from threading import Thread

import xbmc

from resources.lib import streamer, watcher

if __name__ == "__main__":
	monitor = xbmc.Monitor()
	watcher = watcher.LibraryMonitor()
	server = streamer.MyHTTPServer()

	t = Thread(target=server.serve_forever)
	t.setDaemon(True)
	t.start()

	while not monitor.abortRequested():

		if monitor.waitForAbort(1):
			break

	server.server_close()
	server.socket.close()
	server.shutdown()
