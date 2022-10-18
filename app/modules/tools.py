import gi, logging, os, json
gi.require_version('GstPbutils', '1.0')
from gi.repository import GstPbutils
from modules.decorators import singleton
from modules.config import Configs
from urllib import request, parse, error

configs = Configs()
configs.add_module_to_logger(__name__)
logger = logging.getLogger(__name__)

STATIC_RTSP_SERVER_ADDRESS = os.environ.get('STATIC_RSTP_SERVER_ADDRESS')
RTSP_SERVER_DISCOVERY = os.environ.get('RTSP_SERVER_DISCOVERY', 'False').lower() in ('true', '1', 'yes')
RTSP_SERVER_LOCATOR = os.environ.get('RTSP_SERVER_LOCATOR')

@singleton
class StreamDiscovery():
    """Stream probe. Check if a stream is available and get info about it."""
    def __init__(self):
        self.discoverer = GstPbutils.Discoverer()
        self.discoverer.connect('discovered', self.on_discovered)

    def __call__(self, source) -> dict:
        """Check an URI and get stream information

        Args:
            uri (str): URI to check

        Returns:
            dict: Stream capabilities if it's available. Return None otherwise.
        """
        uri = source.uri
        if RTSP_SERVER_DISCOVERY:
            uri = self.get_uri_from_locator(source)
        try:
            info = self.discoverer.discover_uri(uri)
            vstreams = info.get_video_streams()
        except Exception as e:
            logger.error(f"Could not open stream at uri [{uri}]. Error: {e}.")
            return None
        video_info = {'uri': uri,
                'format': '--',
                'format_version': '--',
                'format_specification': '--',
                'width': -1,
                'height': -1,
                'fps': -1}
        if len(vstreams) == 1:
            vcaps = vstreams[0].get_caps().to_string()
            vcaps = vcaps.split(',')

            for prop in vcaps:
                if 'video/' in prop:
                    video_info['format'] = prop
                elif 'version=' in prop:
                    video_info['format_version'] = prop.split(')')[-1]
                elif 'format=' in prop:
                    video_info['format_specification'] = prop.split(')')[-1]
                elif 'width=' in prop:
                    video_info['width'] = int(prop.split(')')[-1])
                elif 'height=' in prop:
                    video_info['height'] = int(prop.split(')')[-1])
                elif 'framerate=' in prop:
                    if 'fraction' in prop:
                        video_info['fps'] = eval(prop.split(')')[-1])
                    elif 'in' in prop:
                        video_info['fps'] = int(prop.split(')')[-1])
                    else:
                        video_info['fps'] = prop.split(')')[-1]
            logger.debug(f"Stream found at uri [{uri}] with properties: [{video_info}]")

            return video_info
        return None

    def on_discovered(self, discoverer, ismedia, infile):
        pass

    def get_uri_from_locator(self, source) -> str:
        """Use the external id of a StreamSource to get a stream uri from a server returned by RTSP_SERVER_LOCATOR

        Args:
            source (StreamSource): a StreamSource object

        Returns:
            str: updated stream uri from a server returned by RTSP_SERVER_LOCATOR
        """
        uri = source.uri
        rtsp_server_adresses_list = [str(source.external_id)]
        rtsp_server_adresses_list = {
            "list": rtsp_server_adresses_list
        }

        data =json.dumps(rtsp_server_adresses_list).encode("utf-8")
        headers = {
            "Content-type" : "application/json"
        }

        try:
            req = request.Request("http://"+RTSP_SERVER_LOCATOR+"/camera/list", data=data, headers=headers)
            resp = request.urlopen(req)
            response = resp.read().decode('utf-8')
            rtsp_server_adresses_list = json.loads(response)
            camid  = rtsp_server_adresses_list[0]['id']
            server = rtsp_server_adresses_list[0]['server'] if rtsp_server_adresses_list[0]['server'] else STATIC_RTSP_SERVER_ADDRESS
            uri = uri.replace("*CAM" + str(camid) + "*", server)

        except error.HTTPError as e:
            logger.error("HTTP error while getting: {} {}".format(e.code, e.reason))

        return uri
    