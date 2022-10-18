import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import time, re
import numpy as np
from datetime import datetime
from threading import Lock
from enum import Enum
from modules.tools import StreamDiscovery
from urllib.parse import urlparse


class BinState(Enum):
    """Possible states of a StreamSource."""
    INITIALIZING = 1
    STARTING = 2
    PAUSED = 3
    PLAYING = 4
    RESETING = 5
    NULL = 6
    FAILURE = 7
    RETRYING = 8
    READY = 9
    REMOVED = 10


class EventPriority(Enum):
    LOW = "BAJA"
    NORMAL = "NORMAL"
    IMPORTANT = "IMPORTANTE"
    CRITICAL = "CRÍTICA"


class Event():
    def __init__(self, event_type: str, time, priority: EventPriority = EventPriority.NORMAL) -> None:
        self._priority = priority
        self._time = self.format_datetime_str(time)
        self._type = event_type

    def format_datetime_str(self, datetime_str) -> str:
        try:
            datetime_str = re.sub(r"[:]|([-](?!((\d{2}[:]\d{2})|(\d{4}))$))", '', datetime_str)
            datetime_str = datetime.strptime(datetime_str, "%Y%m%dT%H%M%S.%f%z")
            datetime_str = datetime_str.strftime("%d/%m/%Y %H:%M:%S")
        except:
            pass
        return datetime_str

    def timestamp_to_datetime(self, timestamp) -> str:
        try:
            datetime_str = datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %H:%M:%S")
        except:
            pass
        return datetime_str

    @property
    def priority(self):
        return self._priority

    @property
    def time(self):
        return self._time

    @property
    def type(self):
        return self._type


class StreamSource():
    """Represent a camera source"""
    def __init__(self, uri: str, name: str, rtsp_reconnect_interval_sec: int, streammux: Gst.Element) -> None:
        """_summary_

        Args:
            uri (str): URI of a RTSP stream
            name (str): Stream alias
            rtsp_reconnect_interval_sec (int): How many seconds before trying to reconnect after last try
            streammux (Gst.Element): Streammux element
        """
        self._bin = None
        self._uri = uri
        self._name = name
        self._label = None
        self._rtsp_reconnect_interval_sec = rtsp_reconnect_interval_sec
        self._streammux = streammux
        self._bin_lock = Lock()
        self._last_reconnect_time = time.time()
        self._last_buffer_time = time.time()
        self._state = BinState.INITIALIZING
        self._pipeline = None
        self._async_state_watch_running = False
        self._source_started = False
        self._status_callback_id = None
        self._internal_id = None
        self._external_id = None
        self._reconfiguring = False
        self._tee = False
        self._last_event = None
        self._in_fallback = False
        self._osd_data = {}
        self._last_availability_check_timestamp = None
        self._availability_check_count = 0
        self._availability_check_time_s = [30,60,120,240,480,960]

    @property
    def bin(self):
        return self._bin

    @property
    def uri(self):
        return self._uri

    @property
    def name(self):
        return self._name

    @property
    def label(self):
        return self._label

    @property
    def rtsp_reconnect_interval_sec(self):
        return self._rtsp_reconnect_interval_sec

    @property
    def streammux(self):
        return self._streammux

    @property
    def last_reconnect_time(self):
        return self._last_reconnect_time

    @property
    def last_buffer_time(self):
        return self._last_buffer_time

    @property
    def state(self):
        return self._state

    @property
    def pipeline(self):
        return self._pipeline

    @property
    def async_state_watch_running(self):
        return self._async_state_watch_running

    @property
    def internal_id(self):
        return self._internal_id

    @property
    def external_id(self):
        return self._external_id

    @property
    def source_started(self):
        return self._source_started

    @property
    def reconfiguring(self):
        return self._reconfiguring

    @property
    def status_callback_id(self):
        return self._status_callback_id

    @property
    def tee(self):
        return self._tee

    @property
    def last_event(self):
        return self._last_event

    @property
    def in_fallback(self):
        return self._in_fallback

    @property
    def osd_data(self):
        return self._osd_data

    @bin.setter
    def bin(self, value):
        self._bin = value

    @name.setter
    def name(self, value):
        self._name = value

    @label.setter
    def label(self, value):
        self._label = value

    @uri.setter
    def uri(self, value):
        self._uri = value

    @state.setter
    def state(self, value):
        self._state = value

    @pipeline.setter
    def pipeline(self, value):
        self._pipeline = value

    @last_buffer_time.setter
    def last_buffer_time(self, time):
        with self._bin_lock:
            self._last_buffer_time = time

    @last_reconnect_time.setter
    def last_reconnect_time(self, time):
        self._last_reconnect_time = time

    @async_state_watch_running.setter
    def async_state_watch_running(self, value):
        self._async_state_watch_running = value

    @internal_id.setter
    def internal_id(self, value):
        self._internal_id = value

    @external_id.setter
    def external_id(self, value):
        self._external_id = value

    @source_started.setter
    def source_started(self, value):
        self._source_started = value

    @reconfiguring.setter
    def reconfiguring(self, value):
        self._reconfiguring = value

    @status_callback_id.setter
    def status_callback_id(self, value):
        self._status_callback_id = value

    @tee.setter
    def tee(self, value):
        self._tee = value

    @last_event.setter
    def last_event(self, value: Event):
        self._last_event = value

    @in_fallback.setter
    def in_fallback(self, value):
        self._in_fallback = value

    @osd_data.setter
    def osd_data(self, value):
        self._osd_data = value

    def should_check_availability(self) -> bool:
        """check whether it's time to check availability or not

        Returns:
            bool: True if it should check availability
        """
        if time.time() - self._last_availability_check_timestamp >= self._availability_check_time_s[self._availability_check_count]:
            return True
        return False

    def stream_is_available(self) -> dict:
        """Check if the stream is available. If it is, return a dictionary with stream properties.

        Returns:
            dict: Result from StreamDiscovery. None if it is not available.
        """
        self._last_availability_check_timestamp = time.time()
        if self._availability_check_count < (len(self._availability_check_time_s) - 1):
            self._availability_check_count += 1
        
        discoverer = StreamDiscovery()
        ret = discoverer(self)

        if ret:
            if not self.same_uris(ret["uri"], self.uri):
                self._uri = ret["uri"]
                self._bin.set_property("uri", self._uri)
            self._availability_check_count = 0

        return ret

    def same_uris(self, uri1: str, uri2: str) -> bool:
        """Comparison between two uri.
        
        Returns:
            bool: True if both uris point to the same path"""
    
        url1_parsed = urlparse(uri1.rstrip("/"))
        url2_parsed = urlparse(uri2.rstrip("/"))

        comparisons = ["scheme", "hostname", "path"]
        for attr in comparisons:
            if getattr(url1_parsed, attr) != getattr(url2_parsed, attr):
                return False
        
        return True

    def reset_availability_check(self) -> None:
        """Reset availability check counter."""
        self._last_availability_check_timestamp = time.time()
        self._availability_check_count = 0