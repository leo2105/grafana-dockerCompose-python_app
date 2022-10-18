import yaml
import os
import logging
import time
from logging.config import dictConfig
from datetime import datetime, timedelta
from modules.decorators import singleton
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler
from typing import Callable
from os import environ

LOGGING_LEVELS = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"]
logging_level = environ.get('LOGGING_LEVEL')
if logging_level is None or logging_level not in LOGGING_LEVELS:
    logging_level = "DEBUG"

LOGGING_CONFIG_DICT = {'formatters': {'simple': {'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'}},
                    'disable_existing_loggers': True,
                    'handlers': {'default': {'class': 'logging.StreamHandler',
                                'formatter': 'simple',
                                'level': f'{logging_level}',
                                'stream': 'ext://sys.stdout'}},
                    'loggers': { __name__: { 'handlers': ['default'], 'level': f'{logging_level}', 'propagate': False},
                                'deepstream_pipeline': { 'handlers': ['default'], 'level': f'{logging_level}', 'propagate': False}},
                    'version': 1}

GST_PLUGINS_CONFIG_PATH_PROPERTY = {"nvdsgst_dsanalytics" : "config-file",
                                    "nvdsgst_inferserver": "config-file-path",
                                    "nvdsgst_infer": "config-file-path"}

dictConfig(LOGGING_CONFIG_DICT)
logger = logging.getLogger(__name__)

DIR_NAMES = ["/app/config/"]

class ConfigChangeHandler(FileSystemEventHandler):
    """Handle changes in observed files"""

    def __init__(self) -> None:
        self.watched_files = {}

    def on_modified(self, event) -> None:
        """Called everytime a file or folder in a watched path changes

        Args:
            event (FileSystemEvent): Event triggered when a change occurs on the monitored file
        """
        logging.info(f'Event type: {event.event_type}  path : {event.src_path}')
        for watched_file_path, watched_file_data in self.watched_files.items():
            if os.path.samefile(watched_file_path, event.src_path):
                if datetime.now() - watched_file_data["last_modified"] < timedelta(seconds=0.5):
                    return
                else:
                    watched_file_data["last_modified"] = datetime.now()
                    event_callback = watched_file_data["callback"]
                    event_callback(watched_file_data)
                break
    
    def start_observer(self, recursive=False) -> None:
        """Start the observer in the config folder

        Args:
            recursive (bool, optional): If watch is recursive. Defaults to False.
        """
        observer = Observer()
        for dir in DIR_NAMES:
            observer.schedule(self, path=dir, recursive=recursive)
        observer.start()

    # Adds a path in the watched files
    def add_watched_file(self, path: str, callback: Callable) -> None:
        """Add a file to be watched

        Args:
            path (str): Path of a file to watch
            callback (Function): Callback function to be called when the file is modified
        """
        value = {"last_modified": datetime.now(), "callback": callback}
        self.watched_files[path] = value
    """
    def add_watched_element_config(self, element: Gst.Element) -> None:
        Add element to watch for changes in it's config file.

        Args:
            element (Gst.Element): Element to be watched
    
        element_type = element.get_factory().get_plugin_name()
        if element_type in GST_PLUGINS_CONFIG_PATH_PROPERTY:
            config_file_property = GST_PLUGINS_CONFIG_PATH_PROPERTY[element_type]
            config_file_path = element.get_property(config_file_property)
            value = {"last_modified": datetime.now(),
                     "callback": self.on_modified_element_config,
                     "element": element,
                     "config_file_property": config_file_property }
            self.watched_files[config_file_path] = value
    """
    def on_modified_element_config(self, watched_file_data: dict) -> None:
        """Callback used to reload element config file when on_modified is triggered.

        Args:
            watched_file_data (dict): Dictionary with information about the element
        """
        element = watched_file_data["element"]
        logger.info(f'{element.get_name()} config file modified')
        time.sleep(0.5)
        try:
            config_file_property = watched_file_data["config_file_property"]
            config_file_path = element.get_property(config_file_property)
            element.set_property(config_file_property, config_file_path) 
            logger.warning(f'{element.get_name()} config file loaded')
        except Exception as e:
            logger.error(f'Error while trying to reload {element.get_name()} config file: {e}')

    def on_created(self,  event):
        """Called everytime a file or folder in a watched path is created."""
        logging.info(f'event type: {event.event_type} path : {event.src_path}')

    def on_deleted(self,  event):
        """Called everytime a file or folder in a watched path is deleted."""
        logging.info(f'event type: {event.event_type} path : {event.src_path}')
    
    
@singleton
class Configs(object):
    """Hold application configuration files read from CONFIG_FOLDER and CONFIG_FILE"""
    def __init__(self) -> None:
        self._logging_config = LOGGING_CONFIG_DICT
        self._config_folder = os.getenv('CONFIG_FOLDER')
        self._app_config_file = os.getenv('CONFIG_FILE')
    
    def get_app_config(self) -> dict:
        """Load, parse and return the application config file in CONFIG_FILE environment variable

        Returns:
            dict: Parsed application config file
        """
        logging.info(f"Loading CFG.")
        with open(self._app_config_file, 'r') as file:
            config = yaml.load(file, Loader=yaml.FullLoader)
            logging.info(f"Config loaded.")
            file.close()
            return config
    
    def get_config_folder(self) -> str:
        """Return CONFIG_FOLDER environment variable

        Returns:
            str: Config folder in CONFIG_FOLDER environment variable
        """
        return self._config_folder

    def get_logging_config(self) -> dict:
        """Return the Dict Config used to log configuration

        Returns:
            dict: Dict Config used to log configuration
        """
        return self._logging_config

    def add_module_to_logger(self, module_name) -> None:
        """Add a module to the logger

        Args:
            module_name (str): Name of the module to add to the logger
        """
        self._logging_config['loggers'].update({module_name: { 'handlers': ['default'], 'level': 'DEBUG', 'propagate': False}})
        dictConfig(self._logging_config)    
    


configs = Configs()
