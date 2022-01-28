import os
import re
import html
import json
import math
import urllib
import difflib
from sqlite3 import dbapi2 as sqlite

import xbmc
import xbmcvfs

from . import encryption
from .PTN.parse import PTN


class StrmUtils:

	def __init__(self):
		self.PTN = PTN()

	def updateLibrary(self, filePath, metadata):
		dirPath, filename = os.path.split(filePath)
		selectStatement = "SELECT idFile FROM files WHERE idPath=(SELECT idPath FROM path WHERE strPath='{}') AND strFilename='{}'".format(dirPath + os.sep, filename)
		dbPath = xbmcvfs.translatePath(self.settings.getSetting("video_db"))

		db = sqlite.connect(dbPath)
		query = list(db.execute(selectStatement))
		db.close()

		if not query:
			return

		fileID = query[0][0]
		videoDuration = float(metadata["durationMillis"]) / 1000
		videoWidth = metadata["width"]
		videoHeight = metadata["height"]
		aspectRatio = float(videoWidth) / videoHeight

		p1 = "INSERT INTO streamdetails (iVideoWidth, iVideoHeight, fVideoAspect, iVideoDuration, idFile, iStreamType)"
		p2 = "SELECT '{}', '{}', '{}', '{}', {}, '0'".format(videoWidth, videoHeight, aspectRatio, videoDuration, fileID)
		p3 = "WHERE NOT EXISTS (SELECT 1 FROM streamdetails WHERE iVideoWidth='{}' AND iVideoHeight='{}' AND fVideoAspect='{}' AND iVideoDuration='{}' AND idFile='{}' AND iStreamType='0')".format(videoWidth, videoHeight, aspectRatio, videoDuration, fileID)

		insertStatement = "{} {} {}".format(p1, p2, p3)
		db = sqlite.connect(dbPath)
		db.execute(insertStatement)
		db.commit()
		db.close()

	@staticmethod
	def createTreeDic(parentFolderID, remotePath):
		return {
			"parent_folder_id": parentFolderID,
			"remote_path": remotePath,
			"files": {
				"strm": [],
				"video": [],
				"subtitles": [],
				"nfo": [],
				"fanart": [],
				"posters": [],
			},
			"dirs": [],
		}

	def getDirectory(self, dirPaths, folderID):
		dirPath = ""

		while folderID not in dirPaths:

			try:
				dirName, folderID = self.cloudService.getDirectory(folderID)
			except KeyError:
				return None, None

			existingPath = dirPaths.get(folderID)

			if existingPath and not dirPath:
				dirPath = existingPath[0]
			if existingPath:
				dirPath = os.path.join(existingPath[0], dirPath)
			else:
				dirPath = os.path.join(dirName, dirPath)

		return dirPath, dirPaths[folderID][1]


	def updateCachedPaths(self, oldPath, newPath, cachedDirectories, folderID):
		cachedDirPath, cachedRootFolderID, cachedParentFolderID, folderIDs, fileIDs = cachedDirectories[folderID]

		if oldPath in cachedDirPath:
			replacement = cachedDirPath.replace(oldPath, newPath)
			cachedDirectories[folderID][0] = replacement

		for folderID in folderIDs:
			self.updateCachedPaths(oldPath, newPath, cachedDirectories, folderID)

	def getGDriveFiles(self, folderID, parentFolderID, path, files, encrypted):
		remoteFiles = self.cloudService.listDir(folderID)

		for file in remoteFiles:
			fileID = file["id"]
			filename = file["name"]
			mimeType = file["mimeType"]
			fileExtension = file.get("fileExtension")

			if encrypted and mimeType == "application/octet-stream" and not fileExtension:
				filename = self.decryptFilename(filename)

				if not filename:
					continue

				fileExtension = filename.rsplit(".", 1)[-1]
				encryptedFile = True

			else:
				encryptedFile = False

			fileType = self.identifyFile(filename, fileExtension, mimeType)

			if not fileType:
				continue

			folderDic = files.get(folderID)

			if not folderDic:
				files[folderID] = self.createTreeDic(parentFolderID, path)

			if fileType == "folder":
				parentFolderID = file["parents"][0]
				newPath = os.path.join(path, filename)
				files[folderID]["dirs"].append(fileID)
				files[fileID] = self.createTreeDic(parentFolderID, newPath)
				self.getGDriveFiles(fileID, parentFolderID, newPath, files, encrypted)
			else:
				metaData = file.get("videoMediaMetadata")
				files[folderID]["files"][fileType].append(
					{
						"filename": filename,
						"id": file["id"],
						"metadata": metaData,
						"encrypted": encryptedFile,
					}
				)

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
			tmdbTitle = self.removeProhibitedFSchars(html.unescape(tmdbTitle))
			titleLowerCase = title.lower()

			tmdbTitleLowerCase = tmdbTitle.lower()
			title = title.lower()
			titleSimilarity = difflib.SequenceMatcher(None, titleLowerCase, tmdbTitleLowerCase).ratio()

			if titleSimilarity > 0.85:
				return tmdbTitle, tmdbYear
			elif tmdbTitleLowerCase in titleLowerCase:
				return tmdbTitle, tmdbYear
			elif titleLowerCase in tmdbTitleLowerCase:
				return tmdbTitle, tmdbYear

	def cleanUpEpisodeTitle(self, title, year, season, episode):

		if season < 10:
			season = "0" + str(season)
		else:
			season = str(season)

		if isinstance(episode, int):

			if episode < 10:
				episode = "0" + str(episode)

		else:
			modifiedEpisode = ""

			for e in episode:
				if e < 10:
					append = "0" + str(e)
				else:
					append = e

				if e != episode[-1]:
					modifiedEpisode += "{}-".format(append)
				else:
					modifiedEpisode += str(append)

			episode = modifiedEpisode

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

	@staticmethod
	def createSTRMContent(driveID, fileID, videoInfo):
		del videoInfo["year"]
		del videoInfo["title"]
		del videoInfo["season"]
		del videoInfo["episode"]
		videoInfo["drive_id"] = driveID
		videoInfo["file_id"] = fileID
		return videoInfo

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

	def pairMediaCompanions(self, mediaExtras, videoFilename, newVideoFilename, fileExtension, dirPath, videoRenamed, originalPath, fileCache, folderID, subtitles=False):

		for mediaExtra in list(mediaExtras):
			filename = self.removeProhibitedFSchars(mediaExtra["filename"])

			if videoFilename in filename:
				fileID = mediaExtra["id"]

				if videoRenamed:

					if subtitles:
						newFilename, fileExtension = os.path.splitext(filename)
						newFilename = newFilename.replace(videoFilename, "").lstrip()
						newFilename = "{}{}{}".format(newVideoFilename, newFilename, fileExtension)
					else:
						newFilename = newVideoFilename + fileExtension

					filePath = self.generateFilePath(dirPath, newFilename)

					if originalPath:
						params = [filePath, filename, folderID, "delete", "original"]
					else:
						params = [filePath, filename, folderID, "delete", "modified"]

				else:
					filePath = self.generateFilePath(dirPath, filename)

					if originalPath:
						params = [filePath, filename, folderID, "rename&delete", "original"]
					else:
						params = [filePath, filename, folderID, "rename&delete", "modified"]

				self.downloadFile(dirPath, filePath, fileID)
				mediaExtras.remove(mediaExtra)
				fileCache[fileID] = params

	def fileProcessor(self, cachedDirectories, cachedFiles, files, folderSettings, remotePath, strmRoot, driveID, parentFolderID):
		folderStructure = folderSettings["folder_structure"]
		fileRenaming = folderSettings["file_renaming"]
		syncNFO = folderSettings["sync_nfo"]
		syncArtwork = folderSettings["sync_artwork"]
		syncSubtitles = folderSettings["sync_subtitles"]

		videoFiles = files.get("video")
		subtitles = files.get("subtitles")
		fanart = files.get("fanart")

		posters = files.get("poster")
		nfos = files.get("nfo")
		strm = files.get("strm")

		fileIDs = cachedDirectories[parentFolderID][4]

		for videoFile in videoFiles:
			filename = videoFile["filename"]
			videoFilename = os.path.splitext(filename)[0]
			fileID = videoFile["id"]
			videoMetadata = videoFile["metadata"]
			encrypted = videoFile["encrypted"]

			metadataRefresh = videoFile.get("metadata_refresh")
			videoInfo = self.getVideoInfo(videoFilename, videoMetadata)
			videoFilename = self.removeProhibitedFSchars(videoFilename)
			strmContent = self.createSTRMContent(driveID, fileID, dict(videoInfo))

			dirPath = remotePath
			newVideoFilename = videoRenamed = strmPath = False
			originalPath = True

			if folderStructure != "original" or fileRenaming != "original":
				videoTitle = videoInfo.get("title")
				videoYear = videoInfo.get("year")
				videoSeason = videoInfo.get("season")
				videoEpisode = videoInfo.get("episode")
				video = False

				if videoEpisode is not None and videoSeason is not None and videoTitle:
					video = "episode"
					showCleanedUp = self.cleanUpEpisodeTitle(videoTitle, videoYear, videoSeason, videoEpisode)

					if showCleanedUp:
						videoSeason = showCleanedUp["season"]
						videoTitle = showCleanedUp["title"]
						newVideoFilename = showCleanedUp["filename"]
					else:
						newVideoFilename = False

				elif videoTitle and videoYear:
					video = "movie"
					newVideoFilename = self.cleanUpMovieTitle(videoTitle, videoYear)

				if folderStructure != "original" and newVideoFilename:

					if video == "movie":
						dirPath = os.path.join(strmRoot, "1. Movies [gDrive]")

						if fileRenaming != "original":
							strmPath = self.generateFilePath(dirPath, newVideoFilename + ".strm")
							videoRenamed = True
						else:
							strmPath = self.generateFilePath(dirPath, videoFilename + ".strm")

					elif video == "episode":
						dirPath = os.path.join(strmRoot, "2. TV [gDrive]", videoTitle, "Season " + videoSeason)

						if fileRenaming != "original":
							strmPath = self.generateFilePath(dirPath, newVideoFilename + ".strm")
							videoRenamed = True
						else:
							strmPath = self.generateFilePath(dirPath, videoFilename + ".strm")

					originalPath = False

				elif fileRenaming != "original" and newVideoFilename:
					strmPath = self.generateFilePath(dirPath, newVideoFilename + ".strm")
					videoRenamed = True

				if syncSubtitles and subtitles:
					self.pairMediaCompanions(subtitles, videoFilename, newVideoFilename, None, dirPath, videoRenamed, originalPath, cachedFiles, parentFolderID, subtitles=True)

				if syncArtwork:

					if fanart:
						self.pairMediaCompanions(fanart, videoFilename, newVideoFilename, "-fanart.jpg", dirPath, videoRenamed, originalPath, cachedFiles, parentFolderID)

					if posters:
						self.pairMediaCompanions(posters, videoFilename, newVideoFilename, "-poster.jpg", dirPath, videoRenamed, originalPath, cachedFiles, parentFolderID)

				if syncNFO and nfos:
					self.pairMediaCompanions(nfos, videoFilename, newVideoFilename, ".nfo", dirPath, videoRenamed, originalPath, cachedFiles, parentFolderID)

			if not strmPath:
				strmPath = self.generateFilePath(dirPath, videoFilename + ".strm")

			self.createStrm(dirPath, strmPath, strmContent, encrypted)

			if metadataRefresh:
				self.updateLibrary(strmPath, videoMetadata)

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

			cachedFiles[fileID] = params

			if fileID not in fileIDs:
				fileIDs.append(fileID)

		unaccountedFiles = []

		if syncSubtitles and subtitles:
			unaccountedFiles += subtitles

		if syncArtwork and (fanart or posters):

			if fanart:
				unaccountedFiles += fanart

			if posters:
				unaccountedFiles += posters

		if syncNFO and nfos:
			unaccountedFiles += nfos

		if strm:
			unaccountedFiles += strm

		if unaccountedFiles:
			self.downloadFiles(unaccountedFiles, remotePath, cachedFiles, parentFolderID, fileIDs)

	def loadEncryption(self):
		saltFile = self.settings.getSetting("crypto_salt")
		saltPassword = self.settings.getSetting("crypto_password")
		self.encryption = encryption.Encryption(saltFile, saltPassword)

	def loadStrmSettings(self):
		strmSettings = self.settings.getSetting("strm")

		if not strmSettings:
			self.strmSettings = {}
		else:
			self.strmSettings = json.loads(strmSettings)

	def saveStrmSettings(self):
		self.settings.setSetting("strm", json.dumps(self.strmSettings))
