import sys
import xbmc
import constants
from threading import Thread
from resources.lib import streamer


def run():
	settings = constants.addon
	pluginName = constants.PLUGIN_NAME
	port = settings.getSettingInt("server_port", 8011)
	server = streamer.MyHTTPServer(("", port), streamer.MyStreamer)

	try:
		pluginHandle = int(sys.argv[1])
		pluginQueries = settings.parse_query(sys.argv[2][1:])
	except:
		pluginHandle = None
		pluginQueries = None

	server.setDetails(pluginHandle, pluginName, pluginName, settings)
	t = Thread(target=server.run)
	t.setDaemon(True)
	t.start()
	monitor = xbmc.Monitor()

	while not monitor.abortRequested():

		if monitor.waitForAbort(1):
			break

	server.socket.close()
	server.shutdown()
