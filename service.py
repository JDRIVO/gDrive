from threading import Thread

import xbmc

import constants
from resources.lib import streamer, watcher

if __name__ == "__main__":
	monitor = xbmc.Monitor()
	watcher = watcher.LibraryMonitor()
	server = streamer.MyHTTPServer(settings=constants.settings)

	t = Thread(target=server.run)
	t.setDaemon(True)
	t.start()

	while not monitor.abortRequested():

		if monitor.waitForAbort(1):
			break

	server.shutdown()
