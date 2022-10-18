import time, re, logging
import tritonclient.grpc as grpcclient
from modules.config import Configs

configs = Configs()
configs.add_module_to_logger(__name__)
logger = logging.getLogger(__name__)

MAX_TRIES = 5
TIME_BETWEEN_TRIES = 10

def is_triton_model_ready(config_file_path: str) -> bool:
    """Returns whether a Triton Model is ready to be used or not.

    Args:
        config_file_path (str): Path to the model's nvinferserver config file

    Returns:
        bool: True is triton model is ready. False otherwise.
    """
    tries = 0

    try:
        with open(config_file_path) as f:
            nvinferserver_cfg_file = f.readlines()
    except FileNotFoundError as e:
        logger.error(f"No such file: '{config_file_path}'")
        return False

    model_data = {"url": None, "model_name": None}
    for line in nvinferserver_cfg_file:
        # using regex to extract only what is inside double quotes
        if "url" in line:
            model_data["url"] = re.findall(r'"([^"]*)"', line)[0]
        elif "model_name" in line:
            model_data["model_name"] = re.findall(r'"([^"]*)"', line)[0]
    if model_data["url"] is not None and model_data["model_name"] is not None:
        logger.info(f"Checking if triton model {model_data['model_name']} is live at url {model_data['url']}.")
        triton_client = grpcclient.InferenceServerClient(url=model_data["url"], verbose=False)
        server_is_live = None
        while True:
            tries += 1
            try:
                if not server_is_live:
                    server_is_live = triton_client.is_server_live()
                else:
                    if triton_client.is_model_ready(model_data["model_name"]):
                        break
                    else:
                        logger.error(f"Model {model_data['model_name']} is not live when trying to check availability. Number of tries: {tries} of {MAX_TRIES}.")                    
            except grpcclient.InferenceServerException as e:
                logger.error(f"Triton Server is not live at url {model_data['url']}. Number of tries: {tries} of {MAX_TRIES}.")
            if tries >= MAX_TRIES:
                return False
            time.sleep(TIME_BETWEEN_TRIES)
        logger.info(f"Triton model {model_data['model_name']} is ready at url {model_data['url']}.")
        triton_client.close()
    else:
        logger.error(f"Model name and server url not found in nvinferserver config file.")
        return False

    return True