import os
import re
import json
import math
import time
import shutil
import urllib
import difflib
import datetime
from threading import Thread

import xbmc
import xbmcgui

from . import gdrive_api
from .PTN.parse import PTN

SUBTITLES = (
	"srt",
	"ssa",
	"vtt",
	"sub",
	"ttml",
	"sami",
	"ass",
	"idx",
	"sbv",
	"stl",
	"smi",
)


class StrmManager:

	def __init__(self, settings, accountManager):
		self.settings = settings
		self.accountManager = accountManager
		self.accounts = self.accountManager.accounts
		self.cloudService = gdrive_api.GoogleDrive(self.accountManager)
		self.PTN = PTN()

		self.monitor = xbmc.Monitor()
		self.dialog = xbmcgui.Dialog()
		self.tasks = {}
		self.taskIDs = []
		self.id = 0

	def run(self):
		self.loadStrmSettings()

		if not self.strmSettings:
			return

		for driveID, driveSettings in self.strmSettings["drives"].items():
			taskDetails = driveSettings["task_details"]
			self.spawnTask(taskDetails, driveID)

	def loadStrmSettings(self):
		strmSettings = self.settings.getSetting("strm")

		if not strmSettings:
			self.strmSettings = {}
		else:
			self.strmSettings = json.loads(strmSettings)

	def saveStrmSettings(self):
		self.settings.setSetting("strm", json.dumps(self.strmSettings))

	@staticmethod
	def identifyFile(filename, fileExtension, mimeType):

		if mimeType == "application/vnd.google-apps.folder":
			return "folder"

		if not fileExtension:
			return

		fileExtension = fileExtension.lower()

		if "video" in mimeType:
			return "video"
		elif fileExtension == "nfo":
			return "nfo"
		elif fileExtension == "jpg":
			fileNameLowerCase = filename.lower()

			if "poster" in fileNameLowerCase:
				return "poster"
			elif "fanart" in fileNameLowerCase:
				return "fanart"

		elif fileExtension in SUBTITLES:
			return"subtitles"

	def getGDriveFiles(self, folderID, path, files):
		remoteFiles = self.cloudService.listDir(folderID)

		for file in remoteFiles:
			fileID = file["id"]
			filename = file["name"]
			mimeType = file["mimeType"]
			fileExtension = file.get("fileExtension")
			fileType = self.identifyFile(filename, fileExtension, mimeType)

			if not fileType:
				continue
			elif fileType == "folder":
				parentFolderID = file["parents"][0]
				newPath = os.path.join(path, filename)
				folderDic = files.get(folderID)
				files[fileID] = {
					"parent_folder_id": parentFolderID,
					"remote_path": newPath,
					"files": {
						"video": [],
						"subtitles": [],
						"nfo": [],
						"fanart": [],
						"posters": [],
					}
				}
				self.getGDriveFiles(fileID, newPath, files)
			else:
				metaData = file.get("videoMediaMetadata")
				folderDic = files.get(folderID)

				if not folderDic:
					files[folderID] = {
						"parent_folder_id": self.cloudService.getDirectory(fileID)[1],
						"remote_path": path,
						"files": {
							"video": [],
							"subtitles": [],
							"nfo": [],
							"fanart": [],
							"posters": [],
						}
					}

				files[folderID]["files"][fileType].append({"filename": filename, "id": file["id"], "metadata": metaData})

		return files

	def getTMDBtitle(self, type, title, year):

		if year:
			params = {"query": "{} y:{}".format(title, year)}
		else:
			params = {"query": title}

		if type == "episode":
			url = "https://www.themoviedb.org/search/tv?" + urllib.parse.urlencode(params)
		else:
			url = "https://www.themoviedb.org/search/movie?" + urllib.parse.urlencode(params)

		headers = {"User-Agent": "Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/532.0 (KHTML, like Gecko) Chrome/3.0.195.38 Safari/532.0"}
		req = urllib.request.Request(url, headers=headers)

		try:
			response = urllib.request.urlopen(req).read().decode("utf-8")
		except urllib.error.URLError as e:
			xbmc.log("gdrive error: " + str(e), xbmc.LOGERROR)
			return

		# url = "https://www.imdb.com/find?" + urllib.parse.urlencode(params)
		# response = self.cloudService.sendPayload(url)
		# imdbTitle = re.findall('fn_al_tt_1" >(?!<img)(.*?)<\/a>', response)
		tmdbResult = re.findall('class="result".*?<h2>(.*?)</h2></a>.*?([\d]{4})', response, re.DOTALL)

		if not tmdbResult and year:
			params = {"query": title}

			if type == "episode":
				url = "https://www.themoviedb.org/search/tv?" + urllib.parse.urlencode(params)
			else:
				url = "https://www.themoviedb.org/search/movie?" + urllib.parse.urlencode(params)

			req = urllib.request.Request(url, headers=headers)

			try:
				response = urllib.request.urlopen(req).read().decode("utf-8")
			except urllib.error.URLError as e:
				xbmc.log("gdrive error: " + str(e), xbmc.LOGERROR)
				return

			tmdbResult = re.findall('class="result".*?<h2>(.*?)</h2></a>.*?([\d]{4})', response, re.DOTALL)

		if tmdbResult:
			tmdbTitle, tmdbYear = tmdbResult[0]
			titleSimilarity = difflib.SequenceMatcher(None, title.lower(), tmdbTitle.lower()).ratio()

			if titleSimilarity > 0.85:
				return tmdbTitle, tmdbYear
			elif tmdbTitle in title:
				return tmdbTitle, tmdbYear
			elif title in tmdbTitle:
				return tmdbTitle, tmdbYear

	def cleanUpEpisodeTitle(self, title, year, season, episode):

		if season < 10:
			season = "0" + str(season)
		if episode < 10:
			episode = "0" + str(episode)

		title = self.getTMDBtitle("episode", title, year)

		if title:
			title, year = title
			return {
				"title": title,
				"season": season,
				"episode": episode,
				"filename": "{} S{}E{}".format(title, season, episode),
			}

	def cleanUpMovieTitle(self, title, year):
		title = self.getTMDBtitle("movie", title, year)

		if title:
			title, year = title
			return "{} ({})".format(title, year)

	def downloadFiles(self, files, dirPath, filenames, folderID, fileIDs):

		for file in list(files):
			fileID = file["id"]
			filename = file["filename"]
			filePath = self.duplicateFileCheck(dirPath, filename)
			self.downloadFile(dirPath, filePath, fileID)
			filenames[fileID] = [
				filename,
				filename,
				folderID,
				"rename&delete",
				"original"
			]

			if fileID not in fileIDs:
				fileIDs.append(fileID)

			files.remove(file)

	def downloadFile(self, dirPath, filePath, fileID):
		self.createDirs(dirPath)
		file = self.cloudService.downloadFile(fileID)

		with open(filePath, "wb") as f:
			f.write(file)

	def createDirs(self, dirPath):

		if not os.path.exists(dirPath):
			os.makedirs(dirPath)

	def createStrm(self, dirPath, strmPath, contents):
		self.createDirs(dirPath)

		with open (strmPath, "w+") as strm:
			url = "plugin://plugin.video.gdrive/?mode=video&encfs=False" + "".join(["&{}={}".format(k, v) for k, v in contents.items() if v])
			strm.write(url)

	@staticmethod
	def createSTRMContent(driveID, fileID, videoInfo):
		del videoInfo["year"]
		del videoInfo["title"]
		del videoInfo["season"]
		del videoInfo["episode"]
		videoInfo["drive_id"] = driveID
		videoInfo["file_id"] = fileID
		return videoInfo

	def getDirectory(self, dirPaths, folderID):
		dirPath = ""

		while folderID not in dirPaths:

			try:
				dirName, folderID = self.cloudService.getDirectory(folderID)
			except KeyError:
				xbmc.log("GET DIRECTORY - KEY ERROR", xbmc.LOGERROR)
				return None, None

			existingPath = dirPaths.get(folderID)

			if existingPath:
				dirPath = os.path.join(existingPath[0], dirPath)
			else:
				dirPath = os.path.join(dirName, dirPath)

		return dirPath, dirPaths[folderID][1]

	@staticmethod
	def deleteFile(filePath):

		if os.path.exists(filePath):
			os.remove(filePath)

		directory = os.path.dirname(filePath)

		try:
			if not os.listdir(directory):
				os.rmdir(directory)
		except:
			# directory doesn't exist
			return

	def rename(self, oldPath, newPath, dirPath=False):

		if os.path.exists(oldPath):

			if dirPath:
				self.createDirs(dirPath)

			shutil.move(oldPath, newPath)

			directory = os.path.dirname(oldPath)

			try:
				if not os.listdir(directory):
					os.rmdir(directory)
			except:
				# directory doesn't exist
				return

		else:
			return "File not found"

	@staticmethod
	def duplicateFileCheck(dirPath, filename):
		filePath = os.path.join(dirPath, filename)
		filename, fileExtension = os.path.splitext(filename)
		copy = 1

		while os.path.exists(filePath):
			filePath = os.path.join(dirPath, "{} ({}){}".format(filename, copy, fileExtension))
			copy += 1

		return filePath

	def pairMediaCompanions(self, mediaExtras, videoFilename, newVideoFilename, fileExtension, dirPath, videoRenamed, originalPath, fileCache, folderID, subtitles=False):

		for mediaExtra in list(mediaExtras):
			filename = mediaExtra["filename"]

			if videoFilename in filename:
				fileID = mediaExtra["id"]

				if newVideoFilename:

					if subtitles:
						newFilename, fileExtension = os.path.splitext(filename)
						newFilename = newFilename.replace(videoFilename, "").lstrip()
						newFilename = "{} {}{}".format(newVideoFilename, newFilename, fileExtension)
					else:
						newFilename = newVideoFilename + fileExtension

				filePath = self.duplicateFileCheck(dirPath, newFilename)
				self.downloadFile(dirPath, filePath, fileID)
				mediaExtras.remove(mediaExtra)

				if videoRenamed:

					if not originalPath:
						params = [filePath, filename, folderID, "delete", "modified"]
					else:
						params = [filePath, filename, folderID, "delete", "original"]

				else:

					if not originalPath:
						params = [filePath, filename, folderID, "delete", "modified"]
					else:
						params = [filePath, filename, folderID, "delete", "original"]

				fileCache[fileID] = params

	def getVideoInfo(self, filename, metaData):

		try:
			videoDuration = float(metaData["durationMillis"]) / 1000
			videoWidth = metaData["width"]
			videoHeight = metaData["height"]
			aspectRatio = float(videoWidth) / videoHeight
		except:
			videoDuration = False
			videoWidth = False
			videoHeight = False
			aspectRatio = False

		videoInfo = self.PTN.parse(filename, standardise=True, coherent_types=False)
		title = videoInfo.get("title")
		year = videoInfo.get("year")
		season = videoInfo.get("season")
		episode = videoInfo.get("episode")

		videoCodec = videoInfo.get("codec")
		hdr = videoInfo.get("hdr")
		audioCodec = videoInfo.get("audio")
		audioChannels = False

		if audioCodec:
			audioCodecList = audioCodec.split(" ")

			if len(audioCodecList) > 1:
				audioCodec = audioCodecList[0]
				audioChannels = int(math.ceil(float(audioCodecList[1])))

		return {
			"title": title,
			"year": year,
			"season": season,
			"episode": episode,
			"video_width": videoWidth,
			"video_height": videoHeight,
			"aspect_ratio": aspectRatio,
			"video_duration": videoDuration,
			"video_codec": videoCodec,
			"audio_codec": audioCodec,
			"audio_channels": audioChannels,
			"hdr": hdr,
		}

	def fileProcessor(self, files, folderSettings, remotePath, strmRoot, driveID, driveSettings, parentFolderID):
		filenames = driveSettings["filenames"]
		folderStructure = folderSettings["folder_structure"]
		fileRenaming = folderSettings["file_renaming"]
		syncNFO = folderSettings["sync_nfo"]
		folderIDs = folderSettings["folder_ids"]

		if parentFolderID not in folderIDs:
			folderIDs.append(parentFolderID)

		fileIDs = folderSettings["file_ids"]
		syncArtwork = folderSettings["sync_artwork"]
		syncSubtitles = folderSettings["sync_subtitles"]
		videoFiles = files.get("video")

		videoTotal = len(videoFiles)
		subtitles = files.get("subtitles")
		fanarts = files.get("fanart")
		posters = files.get("poster")
		nfos = files.get("nfo")

		for videoFile in videoFiles:
			filename = videoFile["filename"]
			videoFilename = os.path.splitext(filename)[0]
			fileID = videoFile["id"]
			videoMetadata = videoFile["metadata"]
			videoInfo = self.getVideoInfo(videoFilename, videoMetadata)

			strmContent = self.createSTRMContent(driveID, fileID, dict(videoInfo))
			strmPath = self.duplicateFileCheck(remotePath, videoFilename + ".strm")
			dirPath = remotePath
			newVideoFilename = videoRenamed = False
			originalPath = True

			if folderStructure != "original" or fileRenaming != "original":
				videoTitle = videoInfo.get("title")
				videoYear = videoInfo.get("year")
				videoSeason = videoInfo.get("season")
				videoEpisode = videoInfo.get("episode")
				video = False

				if videoEpisode and videoSeason and videoTitle:
					video = "episode"
					showCleanedUp = self.cleanUpEpisodeTitle(videoTitle, videoYear, videoSeason, videoEpisode)

					if showCleanedUp:
						videoEpisode = showCleanedUp["episode"]
						videoSeason = showCleanedUp["season"]
						videoTitle = showCleanedUp["title"]
						newVideoFilename = showCleanedUp["filename"]
					else:
						newVideoFilename = False

				elif videoTitle and videoYear:
					video = "movie"
					newVideoFilename = self.cleanUpMovieTitle(videoTitle, videoYear)

				if folderStructure != "original" and video:

					if video == "movie":
						dirPath = os.path.join(strmRoot, "1. Movies [gDrive]")

						if fileRenaming != "original" and newVideoFilename:
							strmPath = self.duplicateFileCheck(dirPath, newVideoFilename + ".strm")
						else:
							strmPath = self.duplicateFileCheck(dirPath, videoFilename + ".strm")

						originalPath = False

					elif video == "episode" and newVideoFilename:
						dirPath = os.path.join(strmRoot, "2. TV [gDrive]", videoTitle, "Season " + videoSeason)
						
						if fileRenaming != "original":
							strmPath = self.duplicateFileCheck(dirPath, newVideoFilename + ".strm")
						else:
							strmPath = self.duplicateFileCheck(dirPath, videoFilename + ".strm")

						videoRenamed = True
						originalPath = False

				elif fileRenaming != "original" and newVideoFilename:
					strmPath = self.duplicateFileCheck(dirPath, newVideoFilename + ".strm")
					videoRenamed = True

				if syncSubtitles and subtitles:
					self.pairMediaCompanions(subtitles, videoFilename, newVideoFilename, None, dirPath, videoRenamed, originalPath, filenames, parentFolderID, subtitles=True)

				if syncArtwork:

					if fanarts:
						self.pairMediaCompanions(fanarts, videoFilename, newVideoFilename, "-fanart.jpg", dirPath, videoRenamed, originalPath, filenames, parentFolderID)

					if posters:
						self.pairMediaCompanions(posters, videoFilename, newVideoFilename, "-poster.jpg", dirPath, videoRenamed, originalPath, filenames, parentFolderID)

				if syncNFO and nfos:
					self.pairMediaCompanions(nfos, videoFilename, newVideoFilename, ".nfo", dirPath, videoRenamed, originalPath, filenames, parentFolderID)

			self.createStrm(dirPath, strmPath, strmContent)

			if videoRenamed:

				if not originalPath:
					params = [strmPath, filename, parentFolderID, "delete", "modified"]
				else:
					params = [os.path.basename(strmPath), filename, parentFolderID, "delete", "original"]

			else:

				if not originalPath:
					params = [strmPath, filename, parentFolderID, "rename&delete", "modified"]
				else:
					params = [os.path.basename(strmPath), filename, parentFolderID, "rename&delete", "original"]

			filenames[fileID] = params
			fileIDs.append(fileID)

		unaccountedFiles = []

		if syncSubtitles and subtitles:
			unaccountedFiles += subtitles

		if syncArtwork and (fanarts or posters):

			if fanarts:
				unaccountedFiles += fanarts

			if posters:
				unaccountedFiles += posters

		if syncNFO and nfos:
			unaccountedFiles += nfos

		if unaccountedFiles:
			self.downloadFiles(unaccountedFiles, remotePath, filenames, parentFolderID, fileIDs)

	def sync(self, driveID):
		account = self.accountManager.getAccount(driveID)
		self.cloudService.setAccount(account)
		self.cloudService.refreshToken()
		driveSettings = self.strmSettings["drives"][driveID]
		apiCall = self.cloudService.getChanges(driveSettings["page_token"])

		changes = apiCall["changes"]
		pageToken = apiCall["newStartPageToken"]
		strmRoot = self.strmSettings["root_path"]
		xbmc.log("THE CHANGES ARE ", xbmc.LOGERROR)
		xbmc.log(json.dumps(changes, sort_keys=True, indent=4), xbmc.LOGERROR)

		if not changes:
			return

		dirPaths = driveSettings["directory_paths"]
		filenames = driveSettings["filenames"]
		folders = driveSettings["folders"]
		newFiles = {}
		deleted = False

		for change in changes:
			file = change["file"]
			fileID = file["id"]
			filename = file["name"]
			mimeType = file["mimeType"]
			parentFolderID = file.get("parents")

			if not parentFolderID:
				# file not inside a folder
				continue

			parentFolderID = parentFolderID[0]

			if file["trashed"]:

				if fileID in filenames:
					cachedFile, cachedFilename, cachedParentFolderID, mode, folderStructure = filenames[fileID]

					if folderStructure == "modified":
						self.deleteFile(cachedFile)
					else:
						filePath = os.path.join(dirPaths[parentFolderID][0], os.path.basename(cachedFile))
						self.deleteFile(filePath)

					del filenames[fileID]
					deleted = True

					if cachedParentFolderID in dirPaths:
						cachedDirPath, cachedRootFolderID, cachedParentFolderID = dirPaths[cachedParentFolderID]

						if cachedRootFolderID in folders:
							folderSettings = folders[cachedRootFolderID]
							fileIDs = folderSettings["file_ids"]

							if fileID in fileIDs:
								fileIDs.remove(fileID)

			else:
				fileExtension = file.get("fileExtension")
				fileType = self.identifyFile(filename, fileExtension, mimeType)

				if not fileType:
					continue

				if fileType == "folder":

					if fileID not in dirPaths:
						dirPath, folderID = self.getDirectory(dirPaths, fileID)

						if folderID:
							dirPath = os.path.join(dirPath, filename)
							dirPaths[fileID] = [dirPath, folderID, parentFolderID]

						continue

					else:
						cachedDirPath, cachedRootFolderID, cachedParentFolderID = dirPaths[fileID]
						dirName = cachedDirPath.split(os.sep)[-1]

						if parentFolderID != cachedParentFolderID and fileID != cachedRootFolderID:
							del dirPaths[fileID]
							dirPath, folderID = self.getDirectory(dirPaths, fileID)

							if dirPath:
								newDirPath = os.path.join(dirPath, filename)
								renameFolder = self.rename(cachedDirPath, newDirPath)
								dirPaths[fileID] = newDirPath, folderID, parentFolderID
							else:
								# Folder moved to another root folder != existing root folder - delete current folder
								# Request files in the dir to be deleted and delete each individual file or perform the more risky and lazy method - delete entire folder
								pass

						elif dirName != filename:
							newDirPath = os.path.join(dirName, filename)
							renameFolder = self.rename(cachedDirPath, newDirPath)
							dirPaths[fileID][0] = newDirPath

						continue

				else:

					if parentFolderID not in dirPaths:
						dirPath, folderID = self.getDirectory(dirPaths, parentFolderID)

						if not folderID:
							continue

					else:
						dirPath, folderID, cachedParentFolderID = dirPaths[parentFolderID]

				if fileID in filenames:
					cachedFile, cachedFilename, cachedParentFolderID, mode, folderStructure = filenames[fileID]

					if folderStructure == "original":
						cachedFilePath = os.path.join(dirPaths[cachedParentFolderID][0], cachedFile)
					else:
						cachedFilePath = cachedFile

					if cachedFilename == filename and os.path.join(dirPaths[cachedParentFolderID][0]) == dirPath:
						# this needs to be done as GDRIVE creates multiple changes for a file, one before its metadata is processed and another change after the metadata is processed
						self.deleteFile(cachedFilePath)
						del filenames[fileID]
					else:

						if mode == "rename&delete":

							if folderStructure == "original":
								fileExtension = os.path.splitext(cachedFile)[1]
								filenameWithoutExt = os.path.splitext(filename)[0]
								newFilename = filenameWithoutExt + fileExtension
								newFilePath = os.path.join(dirPath, newFilename)
								outcome = self.rename(cachedFilePath, newFilePath, dirPath)

								if outcome == "File not found":
									del filenames[fileID]
								else:
									filenames[fileID] = [newFilename, filename, parentFolderID, mode, folderStructure]
									continue

							else:
								fileExtension = os.path.splitext(os.path.basename(cachedFile))[1]
								filenameWithoutExt = os.path.splitext(filename)[0]
								newFilename = filenameWithoutExt + fileExtension
								newFilePath = os.path.join(os.path.dirname(cachedFile), newFilename)
								outcome = self.rename(cachedFilePath, newFilePath)

								if outcome == "File not found":
									del filenames[fileID]
								else:
									filenames[fileID][0] = newFilePath
									continue

						else:
							self.deleteFile(cachedFilePath)
							del filenames[fileID]

				metaData = file.get("videoMediaMetadata")

				if not newFiles:
					newFiles[folderID] = {
						"parent_folder_id": parentFolderID,
						"directory_path": dirPath,
						"video": [],
						"subtitles": [],
						"nfo": [],
						"fanart": [],
						"posters": [],
					}

				newFiles[folderID][fileType].append(
					{
						"parent_folder_id": parentFolderID,
						"directory_path": dirPath,
						"filename": filename,
						"id": fileID,
						"metadata": metaData
					}
				)

		if newFiles:

			for folderID, files in newFiles.items():
				folderSettings = folders[folderID]
				remotePath = files["directory_path"]
				parentFolderID = files["parent_folder_id"]
				self.fileProcessor(files, folderSettings, remotePath, strmRoot, driveID, driveSettings, parentFolderID)

			xbmc.executebuiltin("UpdateLibrary(video,{})".format(strmRoot))

		if deleted:

			if os.name == "nt":
				strmRoot = strmRoot.replace("\\", "\\\\")

			xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.Clean", "params": {"showdialogs": false, "content": "video", "directory": "%s"}}' % strmRoot)

		driveSettings["page_token"] = pageToken
		self.saveStrmSettings()

	@staticmethod
	def strptime(dateString, format):
		return datetime.datetime(*(time.strptime(dateString, format)[0:6]))

	@staticmethod
	def floorDT(dt, interval):
		replace = (dt.minute // interval)*interval
		return dt.replace(minute = replace, second=0, microsecond=0)

	def removeTask(self, driveID):

		if driveID in self.tasks:
			del self.tasks[driveID]

	def spawnTask(self, taskDetails, driveID, startUpRun=True):
		mode = taskDetails["mode"]
		syncTime = taskDetails["frequency"]
		startupSync = taskDetails["startup_sync"]
		self.removeTask(driveID)

		self.id += 1
		id = self.id
		self.taskIDs.append(id)
		self.tasks[driveID] = id

		if mode == "schedule":
			syncTime = self.strptime(syncTime.lstrip(), "%H:%M").time()
			Thread(target=self.scheduledTask, args=(startupSync, syncTime, driveID, id, startUpRun)).start()
		else:
			syncTime = int(syncTime) * 60
			Thread(target=self.intervalTask, args=(startupSync, syncTime, driveID, id, startUpRun)).start()

	def intervalTask(self, startupSync, syncTime, driveID, taskID, startUpRun=True):
		lastUpdate = time.time()

		while True and not self.monitor.abortRequested():

			if taskID not in self.taskIDs:
				return

			if not startupSync and startUpRun:
				startUpRun = False
				continue

			currentTime = time.time()

			if currentTime - lastUpdate < syncTime and not startUpRun:

				if self.monitor.waitForAbort(1):
					# self.saveStrmSettings()
					break

				continue

			startUpRun = False
			self.sync(driveID)
			lastUpdate = time.time()

	def scheduledTask(self, startupSync, syncTime, driveID, taskID, startUpRun=True):

		while True and not self.monitor.abortRequested():

			if taskID not in self.taskIDs:
				return

			if not startupSync and startUpRun:
				startUpRun = False
				continue

			currentTime = self.floorDT(datetime.datetime.now().time(), 1)

			if currentTime != syncTime and not startUpRun:

				if self.monitor.waitForAbort(1):
					# self.saveStrmSettings()
					break

				continue

			startUpRun = False
			self.sync(driveID)

			if self.monitor.waitForAbort(60):
				# self.saveStrmSettings()
				break

	def addTask(self, driveID, folderID, folderName):

		if self.strmSettings:
			gdriveRoot = self.strmSettings["root_path"]
			driveSettings = self.strmSettings["drives"].get(driveID)
		else:
			driveSettings = {}
			gdriveRoot = self.dialog.browse(0, "Select the folder that your files will be stored in", "files")

			if not gdriveRoot:
				return

			gdriveRoot = os.path.join(gdriveRoot, "gDrive")
			self.strmSettings["root_path"] = gdriveRoot
			self.strmSettings["drives"] = {}

		if not driveSettings:
			modes = ["Sync at set inverval", "Sync at set time"]
			selection = self.dialog.select("Sync mode", modes)
			taskDetails = {}

			if selection == -1:
				return

			if selection == 0:
				taskDetails["mode"] = "interval"
				frequency = self.dialog.numeric(0, "Enter the sync interval in minutes")

			else:
				taskDetails["mode"] = "schedule"
				frequency = self.dialog.numeric(2, "Enter the time to sync files")

			if not frequency:
				return

			taskDetails["frequency"] = frequency
			startup = self.dialog.yesno("gDrive", "Sync files at startup?")
			taskDetails["startup_sync"] = startup

			self.strmSettings["drives"][driveID] = {
				"page_token": None,
				"folders": {},
				"last_update": time.time(),
				"filenames": {},
				"directory_paths": {},
				"root_path": os.path.join(gdriveRoot, driveID),
				"task_details": taskDetails,
			}
			driveSettings = self.strmSettings["drives"][driveID]

		else:
			taskDetails = driveSettings["task_details"]

		fileRenaming = self.dialog.yesno("gDrive", "Rename videos to a Kodi friendly format?")

		if not fileRenaming:
			fileRenaming = "original"
		else:
			fileRenaming = "kodi_friendly"

		folderStructure = self.dialog.yesno("gDrive", "Create a Kodi friendly directory structure?")

		if not folderStructure:
			folderStructure = "original"
		else:
			folderStructure = "kodi_friendly"

		syncNFOs = self.dialog.yesno("gDrive", "Sync NFOs?")
		syncArtwork = self.dialog.yesno("gDrive", 'Sync Artwork? "fanart"/"posters" must be included in the filename.')
		syncSubtitles = self.dialog.yesno("gDrive", "Sync Subtitles?")
		self.dialog.notification("gDrive", "Generating files please wait. A notification will appear when this task has completed.")

		driveSettings["folders"][folderID] = {
			"file_ids": [],
			"folder_ids": [],
			"folder_structure": folderStructure,
			"file_renaming": fileRenaming,
			"sync_artwork": syncArtwork,
			"sync_nfo": syncNFOs,
			"sync_subtitles": syncSubtitles,
			"root_path": os.path.join(gdriveRoot, driveID, folderName)
		}

		self.cloudService = gdrive_api.GoogleDrive(self.accountManager)
		account = self.accountManager.getAccount(driveID)
		self.cloudService.setAccount(account)
		self.cloudService.refreshToken()

		strmRoot = self.strmSettings["root_path"]
		folderSettings = driveSettings["folders"][folderID]
		folderRoot = folderSettings["root_path"]
		folders = self.getGDriveFiles(folderID, folderRoot, {})
		driveSettings["directory_paths"][folderID] = [folderRoot, folderID, None]

		for subFolderID, folderInfo in folders.items():
			remotePath = folderInfo["remote_path"]
			parentFolderID = folderInfo["parent_folder_id"]
			dirPath = os.path.join(folderRoot, remotePath)

			driveSettings["directory_paths"][subFolderID] = [dirPath, folderID, parentFolderID]
			files = folderInfo["files"]
			self.fileProcessor(files, folderSettings, dirPath, strmRoot, driveID, driveSettings, subFolderID)

		if not driveSettings.get("page_token"):
			driveSettings["page_token"] = self.cloudService.getPageToken()

		self.saveStrmSettings()
		xbmc.executebuiltin("Container.Refresh")
		self.dialog.notification("gDrive", "Sync Completed")
		self.spawnTask(taskDetails, driveID, startUpRun=False)
