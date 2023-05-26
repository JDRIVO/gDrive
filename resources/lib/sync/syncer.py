import os

import xbmc

from . import cache
from ..ui import dialogs
from .. import filesystem
from ..threadpool import threadpool
from ..filesystem.constants import *
from ..filesystem.folder import Folder


class Syncer:

	def __init__(self, accountManager, cloudService, encrypter, fileOperations, remoteFileProcessor, localFileProcessor, fileTree, settings):
		self.encrypter = encrypter
		self.cloudService = cloudService
		self.accountManager = accountManager
		self.remoteFileProcessor = remoteFileProcessor
		self.localFileProcessor = localFileProcessor
		self.fileTree = fileTree
		self.fileOperations = fileOperations
		self.settings = settings
		self.cache = cache.Cache()

	def sortChanges(self, changes):
		trashed, existingFolders, newFolders, files = [], [], [], []

		for change in changes:
			item = change["file"]

			if item["trashed"]:
				trashed.append(item)
				continue

			item["name"] = filesystem.helpers.removeProhibitedFSchars(item["name"])

			if item["mimeType"] == "application/vnd.google-apps.folder":
				cachedDirectory = self.cache.getDirectory(item["id"])

				if cachedDirectory:
					existingFolders.append(item)
				else:
					newFolders.append(item)

			else:
				files.append(item)

		return trashed + existingFolders + newFolders + files

	def syncChanges(self, driveID):
		account = self.accountManager.getAccount(driveID)
		self.cloudService.setAccount(account)
		self.cloudService.refreshToken()
		syncRootPath = self.cache.getSyncRootPath()
		driveSettings = self.cache.getDrive(driveID)
		drivePath = driveSettings["local_path"]
		changes, pageToken = self.cloudService.getChanges(driveSettings["page_token"])

		if not changes:
			return

		changes = self.sortChanges(changes)
		self.deleted = False
		newFiles = {}
		syncedIDs = []

		for item in changes:
			id = item["id"]

			if id in syncedIDs:
				continue

			syncedIDs.append(id)

			try:
				# shared items that google automatically adds to an account don't have parentFolderIDs
				parentFolderID = item["parents"][0]
			except:
				continue

			if item["trashed"]:
				self.syncDeletions(item, syncRootPath, drivePath)
				continue

			if item["mimeType"] == "application/vnd.google-apps.folder":
				self.syncFolderChanges(item, parentFolderID, driveID, syncRootPath, drivePath, syncedIDs)
			else:
				self.syncFileChanges(item, parentFolderID, driveID, syncRootPath, drivePath, newFiles)

		if newFiles:
			self.syncFileAdditions(newFiles, syncRootPath, driveID)

			if self.settings.getSetting("update_library"):
				xbmc.executebuiltin(f"UpdateLibrary(video,{syncRootPath})")

		if self.deleted and self.settings.getSetting("update_library"):

			if os.name == "nt":
				syncRootPath = syncRootPath.replace("\\", "\\\\")

			xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.Clean", "params": {"showdialogs": false, "content": "video", "directory": "%s"}}' % syncRootPath)

		self.cache.updateDrive({"page_token": pageToken}, driveID)

	def syncDeletions(self, item, syncRootPath, drivePath):
		id = item["id"]
		cachedFiles = True

		if item["mimeType"] == "application/vnd.google-apps.folder":
			cachedFiles = self.cache.getFile(id, "parent_folder_id")
			folderID = id
		else:
			cachedFile = self.cache.getFile(id)

			if not cachedFile:
				return

			self.cache.deleteFile(id)
			folderID = cachedFile["parent_folder_id"]
			cachedDirectory = self.cache.getDirectory(folderID)
			cachedFiles = self.cache.getFile(folderID, "parent_folder_id")

			if cachedFile["original_folder"]:
				dirPath = os.path.join(syncRootPath, drivePath, cachedDirectory["local_path"])
				self.fileOperations.deleteFile(syncRootPath, dirPath, cachedFile["local_name"])
			else:
				filePath = os.path.join(syncRootPath, cachedFile["local_path"])
				self.fileOperations.deleteFile(syncRootPath, filePath=filePath)

		if not cachedFiles:
			cachedDirectory = self.cache.getDirectory(folderID)

			if not cachedDirectory:
				return

			self.cache.deleteDirectory(folderID)

		self.deleted = True

	def syncFolderChanges(self, folder, parentFolderID, driveID, syncRootPath, drivePath, syncedIDs):
		folderID = folder["id"]
		folderName = folder["name"]
		cachedDirectory = self.cache.getDirectory(folderID)

		if not cachedDirectory:
			# new folder added
			dirPath, rootFolderID = self.cloudService.getDirectory(self.cache, folderID)

			if not rootFolderID:
				return

			folderSettings = self.cache.getFolder(rootFolderID)
			self.syncFolderAdditions(syncRootPath, drivePath, dirPath, folderSettings, parentFolderID, folderID, rootFolderID, driveID, syncedIDs)
			return

		# existing folder
		cachedDirectoryPath = cachedDirectory["local_path"]
		cachedParentFolderID = cachedDirectory["parent_folder_id"]
		cachedRootFolderID = cachedDirectory["root_folder_id"]

		if parentFolderID != cachedParentFolderID and folderID != cachedRootFolderID:
			# folder has been moved into another directory
			dirPath, rootFolderID = self.cloudService.getDirectory(self.cache, folderID)

			if dirPath:
				syncedIDs.append(parentFolderID)
				self.cache.updateDirectory({"parent_folder_id": parentFolderID}, folderID)
				cachedDirectory = self.cache.getDirectory(parentFolderID)
				dirPath_ = dirPath
				copy = 1

				if not cachedDirectory:
					parentsParentFolderID = self.cloudService.getParentDirectoryID(parentFolderID)
					directory = {
						"drive_id": driveID,
						"folder_id": parentFolderID,
						"local_path": os.path.split(dirPath)[0],
						"parent_folder_id": parentsParentFolderID if parentsParentFolderID != driveID else parentsParentFolderID,
						"root_folder_id": rootFolderID,
					}
					self.cache.addDirectory(directory)

				while self.cache.getDirectory(dirPath, column="local_path"):
					dirPath = f"{dirPath_} ({copy})"
					copy += 1

				oldPath = os.path.join(syncRootPath, drivePath, cachedDirectoryPath)
				newPath = os.path.join(syncRootPath, drivePath, dirPath)
				self.fileOperations.renameFolder(syncRootPath, oldPath, newPath)
				self.cache.updateChildPaths(cachedDirectoryPath, dirPath, folderID)
			else:
				# folder moved to another root folder != existing root folder - delete current folder
				drivePath = os.path.join(syncRootPath, drivePath)
				self.cache.cleanCache(syncRootPath, drivePath, folderID)
				self.deleted = True

			return

		cachedRemoteName = cachedDirectory["remote_name"]

		if cachedRemoteName != folderName:
			# folder renamed
			cachedDirectoryPathHead, _ = os.path.split(cachedDirectoryPath)
			newDirectoryPath = newDirectoryPath_ = os.path.join(cachedDirectoryPathHead, folderName)
			copy = 1

			while self.cache.getDirectory(newDirectoryPath, column="local_path"):
				newDirectoryPath = f"{newDirectoryPath_} ({copy})"
				copy += 1

			oldPath = os.path.join(syncRootPath, drivePath, cachedDirectoryPath)
			newPath = os.path.join(syncRootPath, drivePath, newDirectoryPath)
			self.fileOperations.renameFolder(syncRootPath, oldPath, newPath)
			self.cache.updateChildPaths(cachedDirectoryPath, newDirectoryPath, folderID)
			self.cache.updateDirectory({"remote_name": folderName}, folderID)

			if folderID == cachedRootFolderID:
				self.cache.updateFolder({"local_path": newDirectoryPath, "remote_name": folderName}, folderID)

	def syncFileChanges(self, file, parentFolderID, driveID, syncRootPath, drivePath, newFiles):
		fileID = file["id"]
		cachedDirectory = self.cache.getDirectory(parentFolderID)
		cachedFile = self.cache.getFile(fileID)

		if not cachedDirectory:
			dirPath, rootFolderID = self.cloudService.getDirectory(self.cache, parentFolderID)

			if not rootFolderID:

				if cachedFile:
					# file has moved outside of root folder hierarchy/tree
					cachedParentFolderID = cachedFile["parent_folder_id"]
					cachedDirectory = self.cache.getDirectory(cachedParentFolderID)

					if cachedFile["original_folder"]:
						cachedFilePath = os.path.join(syncRootPath, drivePath, cachedDirectory["local_path"], cachedFile["local_name"])
					else:
						cachedFilePath = os.path.join(syncRootPath, cachedFile["local_path"])

					self.fileOperations.deleteFile(syncRootPath, filePath=cachedFilePath)
					self.cache.deleteFile(fileID)
					self.deleted = True

				return

			# file added to synced folder but the directory isn't present locally
			dirParentFolderID = self.cloudService.getParentDirectoryID(parentFolderID)
			directory = {
				"drive_id": driveID,
				"folder_id": parentFolderID,
				"local_path": dirPath,
				"parent_folder_id": dirParentFolderID if dirParentFolderID != driveID else parentFolderID,
				"root_folder_id": rootFolderID,
			}
			self.cache.addDirectory(directory)
		else:
			dirPath = cachedDirectory["local_path"]
			cachedParentFolderID = cachedDirectory["parent_folder_id"]
			rootFolderID = cachedDirectory["root_folder_id"]

		folderSettings = self.cache.getFolder(rootFolderID)
		excludedTypes = filesystem.helpers.getExcludedTypes(folderSettings)

		if folderSettings["contains_encrypted"]:
			encrypter = self.encrypter
		else:
			encrypter = None

		file = filesystem.helpers.makeFile(file, excludedTypes, encrypter)

		if not file:
			return

		filename = file.name

		if cachedFile:
			cachedParentFolderID = cachedFile["parent_folder_id"]
			cachedDirectory = self.cache.getDirectory(cachedParentFolderID)
			cachedDirPath = cachedDirectory["local_path"]
			rootFolderID = cachedDirectory["root_folder_id"]

			if cachedFile["original_folder"]:
				cachedFilePath = os.path.join(syncRootPath, drivePath, cachedDirPath, cachedFile["local_name"])
			else:
				cachedFilePath = os.path.join(syncRootPath, cachedFile["local_path"])

			if cachedFile["remote_name"] == filename and cachedDirPath == dirPath:
				# GDrive creates a change after a newly uploaded vids metadata has been processed

				if file.type != "video" or not file.metadata:
					return

				filesystem.helpers.refreshMetadata(file.metadata, cachedFilePath)
				return

			if cachedFile["original_name"]:

				if not os.path.exists(cachedFilePath):
					# file doesn't exist locally - redownload it
					self.cache.deleteFile(fileID)
					self.deleted = True
				else:
					# rename/move file
					newFilename = file.basename + os.path.splitext(cachedFile["local_name"])[1]

					if cachedFile["original_folder"]:
						dirPath = os.path.join(syncRootPath, drivePath, dirPath)
						self.fileOperations.renameFile(syncRootPath, cachedFilePath, dirPath, newFilename)
					else:
						newFilePath = self.fileOperations.renameFile(syncRootPath, cachedFilePath, os.path.dirname(cachedFilePath), newFilename)
						cachedFile["local_path"] = newFilePath

					cachedFile["local_name"] = newFilename
					cachedFile["remote_name"] = filename
					cachedFile["parent_folder_id"] = parentFolderID
					self.cache.updateFile(cachedFile, fileID)
					return

			else:
				# redownload file
				self.fileOperations.deleteFile(syncRootPath, filePath=cachedFilePath)
				self.cache.deleteFile(fileID)
				self.deleted = True

		if not newFiles.get(rootFolderID):
			newFiles[rootFolderID] = {}
			newFiles[rootFolderID][parentFolderID] = Folder(parentFolderID, parentFolderID, dirPath, os.path.join(drivePath, dirPath))
		else:

			if not newFiles[rootFolderID].get(parentFolderID):
				newFiles[rootFolderID][parentFolderID] = Folder(parentFolderID, parentFolderID, dirPath, os.path.join(drivePath, dirPath))

		if file.type in MEDIA_ASSETS:
			mediaAssets = newFiles[rootFolderID][parentFolderID].files["media_assets"]

			if file.ptnName not in mediaAssets:
				mediaAssets[file.ptnName] = []

			mediaAssets[file.ptnName].append(file)
		else:
			newFiles[rootFolderID][parentFolderID].files[file.type].append(file)

	def syncFolderAdditions(self, syncRootPath, drivePath, dirPath, folderSettings, parentFolderID, folderID, rootFolderID, driveID, syncedIDs=None, initialSync=False):

		if folderSettings["contains_encrypted"]:
			encrypter = self.encrypter
		else:
			encrypter = False

		excludedTypes = filesystem.helpers.getExcludedTypes(folderSettings)
		threadCount = self.settings.getSettingInt("thread_count", 1)
		folderRestructure = folderSettings["folder_restructure"]
		fileRenaming = folderSettings["file_renaming"]
		fileTree = self.fileTree.buildTree(folderID, parentFolderID, dirPath, excludedTypes, encrypter, syncedIDs, threadCount)
		folders = []

		if initialSync and self.settings.getSetting("sync_progress_dialog"):
			pDialog = dialogs.SyncProgressionDialog(self.fileTree, heading=f"{self.settings.getLocalizedString(30052)} {folderSettings['remote_name']}")
		else:
			pDialog = False

		with threadpool.ThreadPool(threadCount) as pool:

			for folder in fileTree:
				remotePath = folder.path
				dirPath = os.path.join(drivePath, remotePath)
				folder.path = dirPath
				directory = {
					"drive_id": driveID,
					"folder_id": folder.id,
					"local_path": remotePath,
					"remote_name": folder.name,
					"parent_folder_id": folder.parentID,
					"root_folder_id": rootFolderID,
				}
				self.cache.addDirectory(directory)
				pool.submit(self.remoteFileProcessor.processFiles, folder, folderSettings, dirPath, syncRootPath, driveID, rootFolderID, threadCount, pDialog)

				if folderRestructure or fileRenaming:
					folders.append(folder)

		if pDialog:
			pDialog.close()

		if not folders:
			return

		if pDialog:
			pDialog = dialogs.SyncProgressionDialog(self.fileTree, heading=f"{self.settings.getLocalizedString(30053)} {folderSettings['remote_name']}")

		with threadpool.ThreadPool(threadCount) as pool:

			for folder in folders:
				pool.submit(self.localFileProcessor.processFiles, folder, folderSettings, folder.path, syncRootPath, threadCount, pDialog)

		if pDialog:
			pDialog.close()

	def syncFileAdditions(self, files, syncRootPath, driveID):
		threadCount = self.settings.getSettingInt("thread_count", 1)
		folders = []

		with threadpool.ThreadPool(threadCount) as pool:

			for rootFolderID, directories in files.items():
				folderSettings = self.cache.getFolder(rootFolderID)
				folderRestructure = folderSettings["folder_restructure"]
				fileRenaming = folderSettings["file_renaming"]

				for folderID, folder in directories.items():
					pool.submit(self.remoteFileProcessor.processFiles, folder, folderSettings, folder.path, syncRootPath, driveID, rootFolderID, threadCount)

					if folderRestructure or fileRenaming:
						folders.append((folder, folderSettings))

		with threadpool.ThreadPool(threadCount) as pool:

			for folder, folderSettings in folders:
				pool.submit(self.localFileProcessor.processFiles, folder, folderSettings, folder.path, syncRootPath, threadCount)
