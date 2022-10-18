import json, os, logging
from abc import ABC
from prometheus_client import start_http_server, Gauge
from modules.config import Configs

configs = Configs()
configs.add_module_to_logger(__name__)
logger = logging.getLogger(__name__)


CONFIG_FILE = os.getenv('CONFIG_FILE')

class Broker(ABC):
    """Abstract class representing a broker"""
    def __init__(self) -> None:
        self.cfg = configs.get_app_config()

    def send() -> None:
        """Send message to broker

        Raises:
            NotImplementedError: Should be implemented by subclass
        """
        raise NotImplementedError()

class MessageQueue(Broker):
    def __init__(self) -> None:
        """Abstract class representing a message queue client"""
        super().__init__()
        self.cfg = self.cfg["message-queue"]

    def send(self) -> None:
        """Send message to message queue client

        Raises:
            NotImplementedError: Should be implemented by subclass
        """
        raise NotImplementedError()

class TimeSeriesDb(Broker):
    """Abstract class representing a timeseries database client"""
    def __init__(self) -> None:
        super().__init__()
        self.cfg = self.cfg["timeseries-db"]

    def send(self, data: dict) -> None:
        """Send message to a timeseries database client

        Raises:
            NotImplementedError: Should be implemented by subclass
        """
        raise NotImplementedError()


class PrometheusClient(TimeSeriesDb):
    """Represent a prometheus client"""
    def __init__(self) -> None:
        super().__init__()
        start_http_server(self.cfg["port"])
        self.gauges = {}
        #self.analytics_gauge = Gauge('safecity', 'Value gathered by detector', ['camID', 'metric', 'group', 'host', 'class'])

    def get_gauge(self, measurement: str, labels: list) -> Gauge:
        """Return a Gauge for given measurement and labels. If it doesn't exist, create a new one before returning it.

        Args:
            measurement (str): Measurement for the gauge
            labels (list): Labels for the gauge

        Returns:
            Gauge: Prometheus Gauge with the given measurement and labels
        """
        if measurement not in self.gauges:
            if "measurement_type" in labels and "inference" in labels["measurement_type"]:
                labels.update({"classID": -1})
            else:
                labels.update({"metric": None})
            self.gauges[measurement] = Gauge(measurement, measurement, labels)

        return self.gauges[measurement]


    def send(self, data: dict) -> None:
        """Save data in prometheus

        Args:
            data (dict): Dictionary to break into messages to save to prometheus
        """
        print(data)
        for item in data:
            gauge = self.get_gauge(item["measurement"], item["tags"])
            labelnames = gauge._labelnames
            labels = [0] * len(labelnames)
            for label, value in item["tags"].items():
                labels[labelnames.index(label)] = value
            for k, v in item["fields"].items():
                if "classID" in labelnames:
                    labels[labelnames.index("classID")] = k
                else:
                    labels[labelnames.index("metric")] = k
                try:
                    gauge.labels(*labels).set(v)
                except Exception as e:
                    logger.error(f"It was not possible to log one item to prometheus. Error: {e}")

            
class InfluxdbClient(TimeSeriesDb):
    """Represent a influxdb client"""
    def __init__(self) -> None:
        super().__init__()
        self.host = self.cfg["host"]
        self.port = self.cfg["port"]
        self.db = self.cfg["db"]

        self.client = InfluxDBClient(host=self.host, port=self.port)
        self.dbname = self.db
        dbs = self.client.get_list_database()
        create_db = True
        for db in dbs:
            if db['name']=='dbname':
                create_db = False
                break
        if create_db:
            self.client.create_database(self.dbname)
        self.client.switch_database(self.dbname)

    def send(self, data: dict) -> None:
        """Save data in influxdb

        Args:
            data (dict): Dictionary to write messages in influxdb
        """
        try:
            self.client.write_points(data)
        except Exception as e:
            logger.error(f"It was not possible to send one message to influxdb. Error: {e}")

class KafkaClient(MessageQueue):
    def __init__(self) -> None:
        super().__init__()
        self.host = self.cfg["host"]
        self.port = self.cfg["port"]
        self.main_topic = self.cfg["topic"]

        try:
            self.producer = KafkaProducer(bootstrap_servers=[f"{self.host}:{self.port}"])
        except:
            self.producer = None

    def send(self, data: dict, topic: str=None) -> None:
        """Send data to a kafka topic

        Args:
            data (dict): Message to send to the kafka topic
            topic (str, optional): Topic to send the data to. Defaults to None.
        """
        if not topic:
            topic = self.main_topic 
        if self.producer:
            try:
                self.producer.send(topic, value=json.dumps(data).encode('utf-8'))
            except Exception as e:
                logger.error(f"It was not possible to send one message to Kafka. Error: {e}")

class BrokerFactory:
    """Factory to create instances of Broker."""
    def __init__(self) -> None:
        self._clients = CLIENTS

    def register_client(self, client: str, broker: Broker) -> None:
        """Register a new broker type.

        Args:
            client (str): Name of the broker type to register
            broker (Broker): Broker to register
        """
        self._clients[client] = broker

    def get_client(self, broker_name: str) -> Broker:
        """Return a new broker client of the given type

        Args:
            broker_name (str): Type of Broker the be created

        Raises:
            ValueError: No Broker of given type 

        Returns:
            Broker: Broker of given type 
        """
        client = self._clients.get(broker_name)
        if not client:
            raise ValueError(client)
        logger.info(f"Created a {broker_name} client.")
        return client()


CLIENTS = { "prometheus": PrometheusClient,
            "influxdb": InfluxdbClient,
            "kafka": KafkaClient}
