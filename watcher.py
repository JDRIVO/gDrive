import os
import json
import xbmc
import constants
from sqlite3 import dbapi2 as sqlite


def run():
	watcher = LibraryWatch()
	monitor = xbmc.Monitor()

	while not monitor.abortRequested():

		if monitor.waitForAbort(1) or not watcher.enabled:
			break


class LibraryWatch(xbmc.Monitor):

	def __init__(self):
		self.settings = constants.addon
		self.getSettings()

	def onNotification(self, sender, method, data):

		if method == "VideoLibrary.OnUpdate":
			response = json.loads(data)

			if "item" in response and "type" in response.get("item") and response.get("item").get("type") in ("episode", "movie"):
				dbID = response["item"]["id"]
				dbType = response["item"]["type"]

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

				mediaDetails = self.mediaDetailConversion(strmData)

				if not mediaDetails:
					return

				databaseQuery = self.databaseAction(
					"select",
					(
						"SELECT idFile FROM files WHERE idPath=(SELECT idPath FROM path WHERE strPath=?) AND strFilename=?",
						(strmDir, strmName),
					),
				)
				fileId = databaseQuery[0][0]
				insertParams = []

				for k, v in mediaDetails.items():
					v[0].append("idFile")
					v[1].append(str(fileId))
					reconstruct = "".join(
						[
							"{}='{}' AND ".format(value, v[1][count])
							if value != v[0][-1]
							else "{}='{}'".format(value, v[1][count])
							for count, value in enumerate(v[0])
						]
					)
					rows, values = ", ".join(v[0]), str(v[1])[1:-1]
					insertParams.append(
						"INSERT INTO streamdetails ({}) SELECT {} WHERE NOT EXISTS (SELECT 1 FROM streamdetails WHERE {})".format(
							rows, values, reconstruct
						)
					)

				self.databaseAction("insert", insertParams)

	def openFile(self, path):

		with open(path, "r") as strm:
			return strm.read()

	def mediaDetailConversion(self, strmData):
		# "Apollo 13 (1995) Anniversary Edition&aspect_ratio=33&audio_codec=69"
		splitText = strmData.split("&")

		videoCodes = {
			"video_codec": "strVideoCodec",
			"aspect_ratio": "fVideoAspect",
			"video_width": "iVideoWidth",
			"video_height": "iVideoHeight",
			"video_duration": "iVideoDuration"
		}
		audioCodes = {
			"audio_codec": "strAudioCodec",
			"audio_channels": "iAudioChannels"
		}

		videoRows, videoValues, audioRows, audioValues = [], [], [], []

		for mediaDetail in splitText:
			mediaSplit = mediaDetail.split("=")
			mediaDetail = mediaSplit[0]
			match = False

			if mediaDetail in videoCodes:
				match = True
				rows = videoRows
				values = videoValues
				codes = videoCodes
			elif mediaDetail in audioCodes:
				match = True
				rows = audioRows
				values = audioValues
				codes = audioCodes

			if match:
				value = mediaSplit[1]

				if value:
					rowTitle = codes[mediaDetail]
					rows.append(rowTitle)
					values.append(value)

		converted = {}

		if videoRows:
			videoRows.append("iStreamType")
			videoValues.append("0")
			converted["video"] = [videoRows, videoValues]

		if audioRows:
			audioRows.append("iStreamType")
			audioValues.append("1")
			converted["audio"] = [audioRows, audioValues]

		if converted:
			return converted
		else:
			return None

	def jsonQuery(self, query):
		query = json.dumps(query)
		result = xbmc.executeJSONRPC(query)
		return json.loads(result)

	def databaseAction(self, action, arg):
		db = sqlite.connect(self.dbPath)

		if action == "select":
			cursor = db.execute(arg[0], arg[1])
			result = list(cursor)
			db.close()
			return list(result)

		elif action == "insert":
			# strVideoCodec, iVideoWidth, iVideoHeight, fVideoAspect, iStreamType, idFile
			# 'h264', '1920', '1080', '1.77777777778', '0', '70'
			# strVideoCodec='h264' AND iVideoWidth='1920' AND iVideoHeight='1080' AND fVideoAspect='1.77777777778' AND iStreamType='0' AND idFile='70'

			# cursor = db.execute("INSERT INTO streamdetails (strVideoCodec, strAudioCodec) SELECT 'test1', 'test2' EXCEPT SELECT strVideoCodec, strAudioCodec FROM streamdetails WHERE strVideoCodec='test1' AND strAudioCodec='test2'")
			# cursor = db.execute("INSERT INTO streamdetails (strVideoCodec, strAudioCodec) SELECT 'test1', 'test2' WHERE NOT EXISTS (SELECT strVideoCodec, strAudioCodec FROM streamdetails WHERE strVideoCodec='test1' AND strAudioCodec='test2')")

			for v in arg:
				db.execute(v)

			db.commit()
			db.close()

	def onSettingsChanged(self):
		self.getSettings()

	def getSettings(self):
		self.enabled = self.settings.getSetting("watcher")
		self.dbPath = xbmc.translatePath(self.settings.getSetting("video_db"))
