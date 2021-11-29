import os
import json
import xbmc
import constants
from sqlite3 import dbapi2 as sqlite


def run():
	monitor = xbmc.Monitor()
	watcher = LibraryMonitor()

	while not monitor.abortRequested() and watcher.enabled:

		if monitor.waitForAbort(1):
			break


class LibraryMonitor(xbmc.Monitor):

	def __init__(self):
		self.settings = constants.addon
		self.getSettings()

	@staticmethod
	def openFile(path):

		with open(path, "r") as strm:
			return strm.read()

	@staticmethod
	def jsonQuery(query):
		query = json.dumps(query)
		return json.loads(xbmc.executeJSONRPC(query))

	def onNotification(self, sender, method, data):

		if method != "VideoLibrary.OnUpdate":
			return

		data = json.loads(data)

		if "item" in data and "type" in data.get("item") and data.get("item").get("type") in ("episode", "movie"):
			dbID = data["item"]["id"]
			dbType = data["item"]["type"]

			if dbType == "movie":
				query =	{
					"jsonrpc": "2.0",
					"id": "1",
					"method": "VideoLibrary.GetMovieDetails",
					"params": {"movieid": dbID, "properties": ["file"]},
				}
				jsonKey = "moviedetails"
			else:
				query = {
					"jsonrpc": "2.0",
					"id": "1",
					"method": "VideoLibrary.GetEpisodeDetails",
					"params": {"episodeid": dbID, "properties": ["file"]},
				}
				jsonKey = "episodedetails"

			jsonResponse = self.jsonQuery(query)

			strmPath = jsonResponse["result"][jsonKey]["file"]
			strmName = os.path.basename(strmPath)
			strmDir = os.path.dirname(strmPath) + os.sep
			strmData = self.openFile(strmPath)

			mediaInfo = self.mediaInfoConversion(strmData)

			if not mediaInfo:
				return

			try:
				fileID = self.select(
					(
						"SELECT idFile FROM files WHERE idPath=(SELECT idPath FROM path WHERE strPath=?) AND strFilename=?",
						(strmDir, strmName),
					),
				)
			except:
				xbmc.log(
					self.settings.getLocalizedString(30003) + ": " + self.settings.getLocalizedString(30221),
					xbmc.LOGERROR,
				)
				return

			self.insert(self.statementConstructor(mediaInfo, fileID))

	@staticmethod
	def mediaInfoConversion(strmData):
		videoInfo = {
			"video_codec": "strVideoCodec",
			"aspect_ratio": "fVideoAspect",
			"video_width": "iVideoWidth",
			"video_height": "iVideoHeight",
			"video_duration": "iVideoDuration",
		}
		audioInfo = {
			"audio_codec": "strAudioCodec",
			"audio_channels": "iAudioChannels",
		}
		videoNames, videoValues, audioNames, audioValues = [], [], [], []
		strmData = strmData.split("&")

		for params in strmData:
			name, value = params.split("=")

			if not value:
				continue

			if name in videoInfo:
				videoNames.append(videoInfo[name])
				videoValues.append(value)
			elif name in audioInfo:
				audioNames.append(audioInfo[name])
				audioValues.append(value)

		converted = []

		if videoNames:
			videoNames.append("iStreamType")
			videoValues.append("0")
			converted.append((videoNames, videoValues))

		if audioNames:
			audioNames.append("iStreamType")
			audioValues.append("1")
			converted.append((audioNames, audioValues))

		if converted:
			return converted

	@staticmethod
	def statementConstructor(mediaInfo, fileID):
		statements = []

		for names, values in mediaInfo:
			names.append("idFile")
			values.append(fileID)
			condition = "".join(
				[
					"{}='{}' AND ".format(name, values[count])
					if name != names[-1]
					else "{}='{}'".format(name, values[count])
					for count, name in enumerate(names)
				]
			)
			names = ", ".join(names)
			values = str(values)[1:-1]
			statements.append(
				"INSERT INTO streamdetails ({}) SELECT {} WHERE NOT EXISTS (SELECT 1 FROM streamdetails WHERE {})".format(
					names, values, condition
				)
			)

		return statements

	def select(self, statement):
		db = sqlite.connect(self.dbPath)
		query = list(db.execute(*statement))
		db.close()
		return query[0][0]

	def insert(self, statements):
		db = sqlite.connect(self.dbPath)
		[db.execute(statement) for statement in statements]
		db.commit()
		db.close()

	def onSettingsChanged(self):
		self.getSettings()

	def getSettings(self):
		self.enabled = self.settings.getSetting("watcher")
		self.dbPath = xbmc.translatePath(self.settings.getSetting("video_db"))

	# strVideoCodec, iVideoWidth, iVideoHeight, fVideoAspect, iStreamType, idFile
	# 'h264', '1920', '1080', '1.77777777778', '0', '70'
	# strVideoCodec='h264' AND iVideoWidth='1920' AND iVideoHeight='1080' AND fVideoAspect='1.77777777778' AND iStreamType='0' AND idFile='70'
	# cursor = db.execute("INSERT INTO streamdetails (strVideoCodec, strAudioCodec) SELECT 'test1', 'test2' EXCEPT SELECT strVideoCodec, strAudioCodec FROM streamdetails WHERE strVideoCodec='test1' AND strAudioCodec='test2'")
	# cursor = db.execute("INSERT INTO streamdetails (strVideoCodec, strAudioCodec) SELECT 'test1', 'test2' WHERE NOT EXISTS (SELECT strVideoCodec, strAudioCodec FROM streamdetails WHERE strVideoCodec='test1' AND strAudioCodec='test2')")
