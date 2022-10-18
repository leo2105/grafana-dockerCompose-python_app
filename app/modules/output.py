import gi, logging, json, time, jsonschema
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject
from modules.config import Configs
from modules.debug import save_graph
from threading import Thread
from kafka import KafkaConsumer
from enum import Enum
from abc import ABC
from jsonschema import validate

configs = Configs()
configs.add_module_to_logger(__name__)
logger = logging.getLogger(__name__)

CAMERA_SWITCH_SCHEMA = {
    "type": "object",
    "properties": {
        "host": {"type": "string"},
        "type": {"type": "string"}
    },
    "required": ["host","type"]
}

class OutputPipeline():
    """Create a dynamic output pipeline"""
    def __init__(self, channel: str, on_demand: bool = False) -> None:
        """Initialize a new output pipeline

        Args:
            channel (str): Interpipesink channel to connect to
            on_demand (bool, optional): On demand output. Defaults to False.
        """
        self.pipeline = Gst.Pipeline("output_pipeline")
        self.intervideosrc = Gst.ElementFactory.make("intervideosrc", "intervideosrc")
        self.output_queue = Gst.ElementFactory.make("queue", "output_queue")
        self.config = configs.get_app_config()["output-stream"]
        self.host = configs.get_app_config()["sources-tags"]["host"]

        self.intervideosrc.set_property("channel", channel)

        self.pipeline.add(self.intervideosrc)
        self.pipeline.add(self.output_queue)

        self.intervideosrc.link(self.output_queue)
        self.current_output = None
        self.bin_factory = OutputBinFactory()

        if on_demand:
            self.switch_output("fakesink")
            self.consumer_init()
            GLib.timeout_add(1000, self.keep_alive_check)
        else:
            self.switch_output(self.config["type"])

    def clear_sink_bin(self) -> None:
        """Delete an output bin and all it's elements"""
        if self.pipeline.get_child_by_name("sink_bin") is not None:
            for child in self.sink_bin.children:
                self.sink_bin.remove(child)
            self.pipeline.remove(self.sink_bin)

    def switch_output(self, type: str) -> None:
        """Switch to a output type if it is available

        Args:
            type (str): Output type
        """
        if self.current_output is None or type not in self.current_output.type_name:
            self.set_null_state()
            self.clear_sink_bin()

            try:
                self.current_output = self.bin_factory.get_output_type(type)
                self.sink_bin = self.current_output.bin
                self.pipeline.add(self.sink_bin)
                first_element = self.sink_bin.find_unlinked_pad(Gst.PadDirection.SINK).get_parent()
                self.output_queue.link(first_element)
                self.play()
                logger.warning(f"Switched to a {type} output.")
            except Exception as e:
                logger.error(f"Failed to create output of type {type}. Error: {e}.")

        self.current_output.last_played_ts = time.time()

    def play(self) -> None:
        """Set output bin to PLAYING state"""
        self.pipeline.set_state(Gst.State.PLAYING)

    def set_null_state(self) -> None:
        """Set output bin to NULL state"""
        self.pipeline.set_state(Gst.State.NULL)

    def validate_message_schema(self, message: dict) -> bool:
        """Check if a message is valid

        Args:
            message (dict): Dictionary representing the message

        Returns:
            bool: True if message is valid, False otherwise
        """
        try:
            validate(instance=message, schema=CAMERA_SWITCH_SCHEMA)
        except jsonschema.exceptions.ValidationError as err:
            return False
        return True

    def kafka_consumer_worker(self)  -> None:
        """Consume and process messages from Kafka"""
        for message in self.kafka_consumer:
            if time.time() - message.timestamp / 1000 > 30:
                continue
            message = message.value
            if self.validate_message_schema(message):
                if message["host"] in self.host:
                    logger.debug(f"New message: {message}")
                    if message["type"] in BIN_TYPES:
                        self.switch_output(message["type"])
                    elif "default" in message["type"]:
                        self.switch_output(self.config["type"])
            else:
                logger.info(f"Invalid message received. Message: {message}")

    def keep_alive_check(self) -> bool:
        """Check if a current output needs to be kept alive. If it doesn't, the output is going to fall back to a fakesink.

        Returns:
            bool: Always True because it never should stop
        """
        ts_now = time.time() 
        time_since_last_played = ts_now - self.current_output.last_played_ts
        if "fakesink" not in self.current_output.type_name and time_since_last_played > self.config["on-demand"]["keep-alive"]:
            playing_time = ts_now - self.current_output.created_ts
            self.switch_output("fakesink")
            logger.warning(f"Switched back to fakesink after {playing_time:.2f} seconds of playing time and {time_since_last_played:.2f} seconds without receiving keep-alive message.")
        
        return True

    def consumer_init(self) -> None:
        """Initializes the Kafka consumer and it's thread

        Returns:
            KafkaConsumer: A kafka consumer instance
        """
        self.kafka_consumer = None
        try:
            self.kafka_consumer = KafkaConsumer(self.config["on-demand"]["message-queue"]["topic"],
                                        bootstrap_servers=[f'{self.config["on-demand"]["message-queue"]["host"]}:{self.config["on-demand"]["message-queue"]["port"]}'],
                                        auto_offset_reset='earliest',
                                        enable_auto_commit=True,
                                        group_id= self.host,
                                        value_deserializer=lambda x: json.loads(x.decode('utf-8')))
        except Exception as e:
            logger.error(f"Error while starting kafka client: {e}")
        
        consumer_worker = Thread(target=self.kafka_consumer_worker)
        consumer_worker.daemon = True
        consumer_worker.start()

class OutputBin(ABC):
    """Abstract class representing an output bin"""
    def __init__(self) -> None:
        """Initilizes an output bin"""
        self.config = configs.get_app_config()["output-stream"]
        self.set_type_name()
        self.bin = Gst.Bin.new("sink_bin")
        self.create_bin_elements()
        self.created_ts = time.time()
        self.last_played_ts = None

    def create_bin_elements(self) -> None:
        """Create all elements to be used in the output. All the internal elements should be added to the bin. Elements should be linked if more than one is created.

        Raises:
            NotImplementedError: Should be implemented by subclass
        """
        raise NotImplementedError()

    def set_type_name(self) -> None:
        """Name of the element to be registered to be used as available element in the application config file.

        Raises:
            NotImplementedError: Should be implemented by subclass
        """
        raise NotImplementedError()

    def create_stream_limiter_elements(self) -> None:
        """Create, add and link stream limit elements in the output pipeline. Configurable using the 'output-stream' section in the config file."""
        output_convertor = Gst.ElementFactory.make("videoconvert", "output_convertor"); assert output_convertor
        videoscale = Gst.ElementFactory.make("videoscale", "videoscale"); assert videoscale
        videorate = Gst.ElementFactory.make("videorate", "videorate"); assert videorate
        filter = Gst.ElementFactory.make("capsfilter", "capsfilter"); assert filter
        caps = Gst.Caps.from_string(f"video/x-raw, width={self.config['width']},height={self.config['height']},format={self.config['color-format']},framerate={self.config['framerate']}/1"); assert caps
        filter.set_property("caps", caps)

        self.bin.add(output_convertor)
        self.bin.add(videoscale)
        self.bin.add(videorate)
        self.bin.add(filter)

        output_convertor.link(videoscale)
        videoscale.link(videorate)
        videorate.link(filter)

    def create_udpsink(self) -> Gst.Element:
        """Create and configure an udpsink the output pipeline. Configurable using the 'output-stream' section in the config file.

        Returns:
            Gst.Element: Configured UdpSink element
        """
        udpsink = Gst.ElementFactory.make("udpsink", "udpsink"); assert udpsink
        udpsink.set_property("host", self.config["display"])
        udpsink.set_property("port", self.config["updsink-port-num"])
        udpsink.set_property("sync", 0)

        return udpsink


class ScreenOutputBin(OutputBin):
    """Output bin to show output using the display"""
    def __init__(self) -> None:
        super().__init__()

    def create_bin_elements(self) -> None:
        """Create elements to show the output using the display"""
        output_convertor = Gst.ElementFactory.make("nvvideoconvert", "output_convertor"); assert output_convertor
        sink = Gst.ElementFactory.make("autovideosink", "sink"); assert sink
        sink.set_property("sync", 0)
        self.bin.add(output_convertor)
        self.bin.add(sink)

        output_convertor.link(sink)

    def set_type_name(self) -> None:
        self.type_name = "screen"


class FakeSinkOutputBin(OutputBin):
    """Output bin to drop all buffers"""
    def __init__(self) -> None:
        super().__init__()

    def create_bin_elements(self) -> None:
        """Create fakesink to drop all buffers"""
        sink = Gst.ElementFactory.make("fakesink", "sink")
        sink.set_property("sync", 0)
        
        self.bin.add(sink)
    
    def set_type_name(self) -> None:
        self.type_name = "fakesink"


class HLSSinkOutputBin(OutputBin):
    """Output bin to send encoded H264 buffers via UDP"""
    def __init__(self) -> None:
        super().__init__()
    def create_bin_elements(self) -> None:
        """Create elements to send H264 stream using UDP. Mtu is configurable using the 'output-stream' section in the config file."""
        self.create_stream_limiter_elements()
        
        encoder = Gst.ElementFactory.make("x264enc", "encoder"); assert encoder
        encoder.set_property('bitrate', int(4000000/1000))
        encoder_tune = self.config["encoder-tune"] if "encoder-tune" in self.config else "zerolatency"
        encoder_speed_preset = self.config["encoder-speed-preset"] if "encoder-speed-preset" in self.config else "medium"

        encoder.set_property('tune', encoder_tune)
        encoder.set_property('speed-preset', encoder_speed_preset)
        mpegtsmux = Gst.ElementFactory.make("mpegtsmux" , "mux")
        sink = Gst.ElementFactory.make("hlssink" , "sink")
        stream_limiter_last_element = self.bin.find_unlinked_pad(Gst.PadDirection.SRC).get_parent()
        self.bin.add(encoder, mpegtsmux, sink)
        stream_limiter_last_element.link(encoder)
        encoder.link(mpegtsmux)
        mpegtsmux.link(sink)

        sink.set_property("location", "/hls_output/segment%05d.ts")
        sink.set_property("playlist-location", "/hls_output/playlist.m3u8")
        #sink.set_property("max-files", 3)
        #sink.set_property("target-duration", 30)


    def set_type_name(self) -> None:
        self.type_name = "hls"

class UDPH264SinkOutputBin(OutputBin):
    """Output bin to send encoded H264 buffers via UDP"""
    def __init__(self) -> None:
        super().__init__()

    def create_bin_elements(self) -> None:
        """Create elements to send H264 stream using UDP. Mtu is configurable using the 'output-stream' section in the config file."""
        self.create_stream_limiter_elements()
        encoder = Gst.ElementFactory.make("x264enc", "encoder"); assert encoder
        payloader = Gst.ElementFactory.make("rtph264pay", "rtpgstpay"); assert payloader
        
        encoder.set_property('bitrate', int(4000000/1000))
        encoder_tune = self.config["encoder-tune"] if "encoder-tune" in self.config else "zerolatency"
        encoder_speed_preset = self.config["encoder-speed-preset"] if "encoder-speed-preset" in self.config else "medium"
        encoder.set_property('tune', encoder_tune)
        encoder.set_property('speed-preset', encoder_speed_preset)
        
        if "mtu" in self.config and payloader is not None:
            payloader.set_property("mtu", self.config["mtu"])
        
        stream_limiter_last_element = self.bin.find_unlinked_pad(Gst.PadDirection.SRC).get_parent()

        sink = self.create_udpsink()

        self.bin.add(encoder, payloader, sink)

        stream_limiter_last_element.link(encoder)
        encoder.link(payloader)
        payloader.link(sink)

    def set_type_name(self) -> None:
        self.type_name = "udp-h264"


class UDPGstRawSinkOutputBin(OutputBin):
    """Output bin to send gstreamer raw buffers via UDP. It's not possible to send GPU buffers. Mtu is configurable using the 'output-stream' section in the config file."""
    def __init__(self) -> None:
        super().__init__()

    def create_bin_elements(self) -> None:
        """Create elements to send gstreamer raw buffers using UDP"""
        self.create_stream_limiter_elements()
        payloader = Gst.ElementFactory.make("rtpgstpay", "payloader"); assert payloader
        payloader.set_property("config-interval", 5)

        if "mtu" in self.config and payloader is not None:
            payloader.set_property("mtu", self.config["mtu"])
        
        stream_limiter_last_element = self.bin.find_unlinked_pad(Gst.PadDirection.SRC).get_parent()
        sink = self.create_udpsink()

        self.bin.add(payloader, sink)
        
        stream_limiter_last_element.link(payloader)
        payloader.link(sink)

    def set_type_name(self) -> None:
        self.type_name = "udp-gstraw"


class UDPVideoRawSinkOutputBin(OutputBin):
    """Output bin to send gstreamer raw buffers via UDP. It's not possible to send GPU buffers. Mtu is configurable using the 'output-stream' section in the config file."""
    def __init__(self) -> None:
        super().__init__()

    def create_bin_elements(self) -> None:
        """Create elements to send gstreamer raw buffers using UDP"""
        self.create_stream_limiter_elements()
        payloader = Gst.ElementFactory.make("rtpvrawpay", "payloader"); assert payloader

        if "mtu" in self.config and payloader is not None:
            payloader.set_property("mtu", self.config["mtu"])
        
        stream_limiter_last_element = self.bin.find_unlinked_pad(Gst.PadDirection.SRC).get_parent()
        sink = self.create_udpsink()

        self.bin.add(payloader, sink)
        
        stream_limiter_last_element.link(payloader)
        payloader.link(sink)

    def set_type_name(self) -> None:
        self.type_name = "udp-videoraw"


class OutputBinFactory:
    """Factory to create instances of OutputBin."""
    def __init__(self) -> None:
        self._bin_types = BIN_TYPES

    def register_output_type(self, type: str, output_bin: OutputBin):
        """Register a new output type.

        Args:
            type (str): Name of the type to register
            output_bin (OutputBin): OutputBin to register
        """
        self._bin_types[type] = output_bin

    def get_output_type(self, type: str) -> OutputBin:
        """Return a new output of the given type

        Args:
            type (str): Type of OutputBin the be created

        Raises:
            ValueError: No OutputBin of given type 

        Returns:
            OutputBin: OutputBin of given type 
        """
        output_bin = self._bin_types.get(type)
        if not output_bin:
            raise ValueError(output_bin)
        logger.info(f"OutputBinFactory creating a {type} output bin.")
        return output_bin()


BIN_TYPES = {"fakesink": FakeSinkOutputBin,
             "screen": ScreenOutputBin,
             "udp-h264": UDPH264SinkOutputBin,
             "udp-gstraw": UDPGstRawSinkOutputBin,
             "udp-videoraw": UDPVideoRawSinkOutputBin,
             "hls-sink": HLSSinkOutputBin
            }
