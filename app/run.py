import sys, json, queue, os, logging, random, time, cv2
import numpy as np
from datetime import timezone, datetime
from threading import Lock, Thread
from modules.clients import BrokerFactory
from modules.config import Configs

configs = Configs()
configs.add_module_to_logger(__name__)
logger = logging.getLogger("SmartCity-Lab")

class Main():
    def __init__(self):
        self.metrics_queue = queue.Queue()
        self.metrics_sent = 0.
        self.cfg = configs.get_app_config()
        self.extra_tags = []
        if "sources-tags" in self.cfg:
            self.extra_tags = self.cfg["sources-tags"]
            logger.info(f'Extra tags: {self.extra_tags}')
        self.custom_init()
    """
    def run(self):
        t = time.time()
        while True:
            t_aux = time.time()
            if t_aux - t > 1: # Each 1 sec send info  
                data = {
                        'camID' : 0,
                        'pessoasEntrando': random.randint(1,5)
                    }
                dt_now = datetime.now(timezone.utc).astimezone().isoformat()
                self.save_metrics(data, dt_now) # funcao para enviar dados para prometheus
                print(data)
                t = t_aux
    """
    
    def run_2(self):
        lines = open('log.txt', 'r').read().split('\n')
        for line in lines[:-1]:
            line_arr = line.split(',')
            data  = {
                'camID' : line_arr[0],
                #'dt_now' : f"{str(line_arr[1][1:]).replace(' ','T')}.626881-05:00",
                'person_status' : line_arr[2][1:],
                'people_count' : line_arr[3][1:]
            }
            dt_now = f"{str(line_arr[1][1:]).replace(' ','T')}.626881-05:00"
            #print(data, dt_now)
            self.save_metrics(data, dt_now)
            time.sleep(1)

    def custom_init(self) -> None:
        """Initialize brokers, probes and handlers for this profile. Overriding custom_init method from base."""
        self.pgie_classes_str = ["person", "bag", "face"]
        self.brokers_init()

    def brokers_init(self) -> None:
        """Initialize message queue and timeseries database clients."""
        broker_factory = BrokerFactory()
        self.timeseries_db_client = broker_factory.get_client(self.cfg["timeseries-db"]["target"])

        self.newReg = {}
        self.account = {}
        for k in self.pgie_classes_str: self.newReg[k]=0
        metricSaver = Thread(target=self.metricSaverWorker)
        metricSaver.daemon = True
        metricSaver.start()

    def save_metrics(self, data: dict, dt_now: str) -> None:
        """Process inference data sent from probes, create messages and save them.

        Args:
            data (dict): Dictionary with data to be saved
        """
        messages_dict = {"timeseries_db": []}
        #dt_now = datetime.now(timezone.utc).astimezone().isoformat()
        #print(dt_now, type(dt_now))

        # Custom message
        objs_in_frame = {"measurement": "KPI_1",
                        "tags": {"measurement_type": "inference"},
                        #"time": str(data['dt_now']),
                        "time": dt_now,
                        "fields": data}
        messages_dict["timeseries_db"].append(objs_in_frame)

        if len(self.extra_tags)>0:
            for messages in messages_dict.values():
                for message in messages:
                    message["tags"].update(self.extra_tags)

        self.send_message(messages_dict)
    
    def send_message(self, message: dict) -> None:
        """Add a single message in the metrics queue

        Args:
            message (dict): Metrics to be sent to a message queue or timeseries database
        """
        try:
            self.metrics_queue.put(message)
        except Exception as e:
            logger.error(f'Error sending message to queue: {e}')


    def metricSaverWorker(self) -> None:
        """Listen to metrics_queue and save metrics in timeseries database."""
        while True:
            try:
                messages_dict = self.metrics_queue.get(timeout=1)
            except queue.Empty:
                continue
            if "stop_worker" in messages_dict:
                logger.warning(f'Metrics saver worker: stop_worker message received.')
                break
            if(len(messages_dict)==0): 
                continue

            for target, messages in messages_dict.items():
                if "timeseries_db" in target:
                    for message in messages:
                        if isinstance(message["time"], tuple):
                            message["time"] = message["time"][0]
                    self.timeseries_db_client.send(messages)

            self.metrics_sent+=1
        logger.warning(f'{datetime.now().isoformat()} Metrics Saver Loop ENDED')


obj = Main()
#obj.run()
obj.run_2()
