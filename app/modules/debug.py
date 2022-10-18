import os, gi, json, subprocess, logging
gi.require_version('Gst', '1.0')
from gi.repository import Gst
from datetime import datetime, timezone
from modules.config import Configs

configs = Configs()

configs.add_module_to_logger(__name__)
logger = logging.getLogger(__name__)

DEBUG_FOLDER = os.environ.get('DEBUG_FOLDER')
GRAPHS_FOLDER = os.environ.get('GST_DEBUG_DUMP_DOT_DIR')
GPU_STATS_FOLDER = f"{os.environ.get('DEBUG_FOLDER')}/gpu_stats"

def save_graph(pipeline: Gst.Pipeline, event: str, graph_name: str, save_gpu_stats: bool = False) -> None:
    """Save a pipeline's graph

    Args:
        pipeline (Gst.Pipeline): Pipeline to generate a graph
        event (str): Reason the create a graph
        graph_name (str): Name of the graph to be usaed as a prefix
        save_gpu_stats (bool, optional): Save gpu stats json. Defaults to False.
    """
    time = datetime.now(timezone.utc).astimezone().isoformat()
    os.makedirs(GRAPHS_FOLDER, exist_ok=True)
    dotfile = os.path.abspath(f"{GRAPHS_FOLDER}/{graph_name}_{event}_{time}.dot")
    pngfile = os.path.abspath(f"{GRAPHS_FOLDER}/{graph_name}_{event}_{time}.png")
    if os.access(dotfile, os.F_OK):
        os.remove(dotfile)
    if os.access(pngfile, os.F_OK):
        os.remove(pngfile)

    Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL, f"{graph_name}_{event}_{time}")
    try:
        subprocess.Popen(["/usr/bin/dot","-Tpng","-o",pngfile,dotfile]).wait(timeout=30)
    except Exception as e:
        print("Timeout while trying to convert the dot file to a png.")
