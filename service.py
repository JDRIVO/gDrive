import xbmc
import server
import watcher
from threading import Thread

if __name__ == "__main__":
	t = Thread(target=server.run)
	t.setDaemon(True)
	t.start()
	t = Thread(target=watcher.run)
	t.setDaemon(True)
	t.start()
	monitor = xbmc.Monitor()

	while not monitor.abortRequested():

		if monitor.waitForAbort(1):
			break
