import os
import re
import threading
from ..threadpool import threadpool

from . import helpers
from .constants import *


class RemoteFileProcessor:

	def __init__(self, cloudService, fileOperations, settings, cache):
		self.cloudService = cloudService
		self.fileOperations = fileOperations
		self.settings = settings
		self.cache = cache

	def processFiles(
		self,
		folder,
		folderSettings,
		drivePath,
		syncRootPath,
		driveID,
		rootFolderID,
		threadCount,
		progressDialog=False,
	):
		files = folder.files
		parentFolderID = folder.id
		syncRootPath = syncRootPath + os.sep
		remoteDirPath = os.path.join(drivePath, folder.path)
		dirPath = os.path.join(syncRootPath, remoteDirPath)
		folderRestructure = folderSettings["folder_restructure"]
		fileRenaming = folderSettings["file_renaming"]
		videos = files.get("video")
		mediaAssets = files.get("media_assets")
		strm = files.get("strm")
		cachedFiles = []

		if strm:

			with threadpool.ThreadPool(threadCount) as pool:
				[
					pool.submit(
						self.processSTRM,
						file,
						dirPath,
						driveID,
						rootFolderID,
						parentFolderID,
						cachedFiles,
						progressDialog,
					) for file in strm
				]

		if folderRestructure or fileRenaming:
			dirPath = os.path.join(syncRootPath, "[gDrive] Processing", remoteDirPath)
			originalFolder = False
		else:
			originalFolder = True

		if videos:

			with threadpool.ThreadPool(threadCount) as pool:
				[
					pool.submit(
						self.processVideo,
						video,
						syncRootPath,
						dirPath,
						driveID,
						rootFolderID,
						parentFolderID,
						cachedFiles,
						originalFolder,
						progressDialog,
					) for video in videos
				]

		if mediaAssets:

			with threadpool.ThreadPool(threadCount) as pool:
				[
					pool.submit(
						self.processMediaAssets,
						assets,
						syncRootPath,
						dirPath,
						driveID,
						rootFolderID,
						parentFolderID,
						cachedFiles,
						originalFolder,
						progressDialog,
					) for assetName, assets in mediaAssets.items() if assets
				]

		self.cache.addFiles(cachedFiles)

	def processMediaAssets(
		self,
		mediaAssets,
		syncRootPath,
		dirPath,
		driveID,
		rootFolderID,
		parentFolderID,
		cachedFiles,
		originalFolder,
		progressDialog,
	):

		for file in mediaAssets:
			fileID = file.id
			remoteName = file.name
			filePath = self.fileOperations.downloadFile(dirPath, remoteName, fileID, modifiedTime=file.modifiedTime, encrypted=file.encrypted)
			localName = os.path.basename(filePath)
			file.name = localName
			file = (
				driveID,
				rootFolderID,
				parentFolderID,
				fileID,
				filePath.replace(syncRootPath, "") if not originalFolder else False,
				localName,
				remoteName,
				True,
				originalFolder,
			)
			cachedFiles.append(file)

			if progressDialog:
				progressDialog.processFile(remoteName)

	def processSTRM(
		self,
		file,
		dirPath,
		driveID,
		rootFolderID,
		parentFolderID,
		cachedFiles,
		progressDialog,
	):
		fileID = file.id
		remoteName = file.name
		filePath = self.fileOperations.downloadFile(dirPath, remoteName, fileID, modifiedTime=file.modifiedTime, encrypted=file.encrypted)
		localName = os.path.basename(filePath)
		file = (
			driveID,
			rootFolderID,
			parentFolderID,
			fileID,
			False,
			localName,
			remoteName,
			True,
			True,
		)
		cachedFiles.append(file)

		if progressDialog:
			progressDialog.processFile(remoteName)

	def processVideo(
		self,
		file,
		syncRootPath,
		dirPath,
		driveID,
		rootFolderID,
		parentFolderID,
		cachedFiles,
		originalFolder,
		progressDialog,
	):
		fileID = file.id
		remoteName = file.name
		filename = f"{file.basename}.strm"
		strmContent = helpers.createSTRMContents(driveID, fileID, file.encrypted, file.contents)
		filePath = self.fileOperations.createFile(dirPath, filename, strmContent, modifiedTime=file.modifiedTime, mode="w+")
		localName = os.path.basename(filePath)
		file.name = localName
		file = (
			driveID,
			rootFolderID,
			parentFolderID,
			fileID,
			filePath.replace(syncRootPath, "") if not originalFolder else False,
			localName,
			remoteName,
			True,
			originalFolder,
		)
		cachedFiles.append(file)

		if progressDialog:
			progressDialog.processFile(remoteName)

class LocalFileProcessor:

	def __init__(self, cloudService, fileOperations, settings, cache):
		self.cloudService = cloudService
		self.fileOperations = fileOperations
		self.settings = settings
		self.cache = cache
		self.imdbLock = threading.Lock()

	def processFiles(
		self,
		folder,
		folderSettings,
		drivePath,
		syncRootPath,
		threadCount,
		progressDialog=False,
	):
		files = folder.files
		syncRootPath = syncRootPath + os.sep
		remoteDirPath = os.path.join(drivePath, folder.path)
		processingDirPath = os.path.join(syncRootPath, "[gDrive] Processing", remoteDirPath)
		dirPath = os.path.join(syncRootPath, remoteDirPath)
		videos = files.get("video")
		mediaAssets = files.get("media_assets")

		if progressDialog:
			strm = files.get("strm")

			if strm:
				progressDialog.incrementFiles(len(strm))

		if videos:
			folderRestructure = folderSettings["folder_restructure"]
			fileRenaming = folderSettings["file_renaming"]
			tmdbSettings = {"api_key": "98d275ee6cbf27511b53b1ede8c50c67"}

			for key, value in {"tmdb_language": "language", "tmdb_region": "region", "tmdb_adult": "include_adult"}.items():

				if folderSettings[key]:
					tmdbSettings[value] = folderSettings[key]

			with threadpool.ThreadPool(threadCount) as pool:
				[
					pool.submit(
						self.processVideo,
						video,
						mediaAssets,
						folderSettings,
						syncRootPath,
						dirPath,
						processingDirPath,
						folderRestructure,
						fileRenaming,
						tmdbSettings,
						progressDialog,
					) for video in videos
				]

		if mediaAssets:

			with threadpool.ThreadPool(threadCount) as pool:
				[
					pool.submit(
						self.processMediaAssets,
						assets,
						syncRootPath,
						dirPath,
						processingDirPath,
						None,
						True,
						True,
						progressDialog,
					) for assetName, assets in mediaAssets.items() if assets
				]

	def processMediaAssets(
		self,
		mediaAssets,
		syncRootPath,
		dirPath,
		processingDirPath,
		videoFilename,
		originalName,
		originalFolder,
		progressDialog,
	):

		for file in list(mediaAssets):
			fileID = file.id
			remoteName = file.name
			assetType = file.type
			fileExtension = f".{file.extension}"

			if not originalName:

				if assetType == "subtitles":
					language = ""

					if file.language:
						language += f".{file.language}"

					if re.search("forced\.[\w]*$", remoteName, re.IGNORECASE):
						language += ".Forced"

					fileExtension = f"{language}{fileExtension}"

				elif assetType in ARTWORK:
					fileExtension = f"-{assetType}{fileExtension}"

				filename = f"{videoFilename}{fileExtension}"
			else:
				filename = remoteName

			filePath = os.path.join(processingDirPath, remoteName)
			filePath = self.fileOperations.renameFile(syncRootPath, filePath, dirPath, filename)
			mediaAssets.remove(file)

			if progressDialog:
				progressDialog.processRenamedFile(file.name)

			file = {
				"local_path": filePath.replace(syncRootPath, "") if not originalFolder else False,
				"local_name": os.path.basename(filePath),
				"original_name": originalName,
				"original_folder": originalFolder,
			}
			self.cache.updateFile(file, fileID)

	def processVideo(
		self,
		file,
		mediaAssets,
		folderSettings,
		syncRootPath,
		dirPath,
		processingDirPath,
		folderRestructure,
		fileRenaming,
		tmdbSettings,
		progressDialog,
	):
		fileID = file.id
		mediaType = file.media
		ptnName = file.ptnName
		filename = f"{file.basename}.strm"
		filePath = os.path.join(processingDirPath, filename)
		originalName = originalFolder = True
		newFilename = False

		if mediaType in ("episode", "movie"):
			modifiedName = file.formatName(tmdbSettings, self.imdbLock)
			newFilename = modifiedName.get("filename") if modifiedName else False

			if newFilename:

				if fileRenaming:
					filename = f"{newFilename}.strm"
					originalName = False

				if folderRestructure:

					if mediaType == "movie":
						dirPath = os.path.join(syncRootPath, "[gDrive] Movies", newFilename)
					else:
						dirPath = os.path.join(
							syncRootPath,
							"[gDrive] Series",
							f"{modifiedName['title']} ({modifiedName['year']})",
							f"Season {file.season}",
						)

					originalFolder = False

		if ptnName in mediaAssets:
			self.processMediaAssets(
				mediaAssets[ptnName],
				syncRootPath,
				dirPath,
				processingDirPath,
				newFilename,
				originalName,
				originalFolder,
				progressDialog,
			)

		filePath = self.fileOperations.renameFile(syncRootPath, filePath, dirPath, filename)

		if progressDialog:
			progressDialog.processRenamedFile(file.name)

		file = {
			"local_path": filePath.replace(syncRootPath, "") if not originalFolder else False,
			"local_name": os.path.basename(filePath),
			"original_name": originalName,
			"original_folder": originalFolder,
		}
		self.cache.updateFile(file, fileID)
