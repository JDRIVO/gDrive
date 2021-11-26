import xbmc
from threading import Thread

class GPlayer(xbmc.Player):

	def __init__(self, dbID, dbType, widget, trackProgress, settings):
		self.videoDuration = self.stopSaving = self.started = self.close = False
		self.dbID = dbID
		self.dbType = dbType
		self.widget = widget
		self.settings = settings
		self.trackProgress = trackProgress

		if self.dbType == "movie":
			self.isMovie = True
			self.markedWatchedPoint = float(self.settings.getSetting("movie_watch_time"))
		else:
			self.isMovie = False
			self.markedWatchedPoint = float(self.settings.getSetting("tv_watch_time"))

		xbmc.sleep(2000)

		while not self.videoDuration:

			try:
				self.videoDuration = self.getTotalTime()
			except:
				self.close = True
				return

			xbmc.sleep(100)

		if self.trackProgress: Thread(target=self.saveProgress).start()
		self.started = True

	def onPlayBackStarted(self):
		if not self.started: return
		self.stopSaving = True
		if self.trackProgress: self.updateProgress(False)
		self.close = True

	def onPlayBackEnded(self):
		self.close = True

	def onPlayBackStopped(self):

		if self.trackProgress:
			self.updateProgress(False)
		else:
			xbmc.executebuiltin("Container.Refresh")

		self.close = True

	def onPlayBackSeek(self, time, seekOffset):
		self.time = time

	def saveProgress(self):

		while self.isPlaying() and not self.stopSaving:

			try:
				self.time = self.getTime()
			except:
				pass

			self.updateProgress()
			xbmc.sleep(1000)

	def updateProgress(self, thread=True):

		try:
			videoProgress = self.time / self.videoDuration * 100
		except:
			return

		if videoProgress < self.markedWatchedPoint:
			watched = False
			func = self.updateResumePoint
		else:
			watched = True
			func = self.markVideoWatched

		if thread:
			func()
		else:

			if (watched or self.time < 180) and self.widget and self.isMovie:
				func()
				self.refreshVideo()
				return

			for _ in range(3):
				func()
				xbmc.sleep(1000)

	def updateResumePoint(self):

		if self.isMovie:
			xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails", "params": {"movieid": %s, "playcount": 0, "resume": {"position": %d, "total": %d}}}' % (self.dbID, self.time, self.videoDuration))
		else:
			xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetEpisodeDetails", "params": {"episodeid": %s, "playcount": 0, "resume": {"position": %d, "total": %d}}}' % (self.dbID, self.time, self.videoDuration))

	def markVideoWatched(self):

		if self.isMovie:
			xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetMovieDetails", "params": {"movieid": %s, "playcount": 1, "resume": {"position": 0, "total": 0}}}' % self.dbID)
		else:
			xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.SetEpisodeDetails", "params": {"episodeid": %s, "playcount": 1, "resume": {"position": 0, "total": 0}}}' % self.dbID)

	def refreshVideo(self):

		if self.isMovie:
			xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.RefreshMovie", "params": {"movieid": %s}}' % self.dbID)
		else:
			xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.RefreshEpisode", "params": {"episodeid": %s}}' % self.dbID)
