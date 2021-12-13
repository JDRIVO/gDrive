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
	server.setDetails(pluginName, settings)

	t = Thread(target=server.run)
	t.setDaemon(True)
	t.start()
	monitor = xbmc.Monitor()

	while not monitor.abortRequested():

		if monitor.waitForAbort(1):
			break

	server.socket.close()
	server.shutdown()
