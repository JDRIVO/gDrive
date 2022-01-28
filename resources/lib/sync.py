import os

import xbmc


class Sync:

	def syncChanges(self, driveID):
		self.loadEncryption()
		account = self.accountManager.getAccount(driveID)
		self.cloudService.setAccount(account)
		self.cloudService.refreshToken()
		driveSettings = self.strmSettings["drives"][driveID]

		getChanges = self.cloudService.getChanges(driveSettings["page_token"])
		changes = getChanges["changes"]
		pageToken = getChanges["newStartPageToken"]
		strmRoot = self.strmSettings["root_path"]
		cachedDirectories = driveSettings["directories"]

		if not changes:
			return

		cachedDirectories = driveSettings["directories"]
		cachedFiles = driveSettings["files"]
		folders = driveSettings["folders"]
		newFiles = {}
		deleted = False

		for change in changes:
			fileProperties = change["file"]
			fileID = fileProperties["id"]
			filename = fileProperties["name"]
			mimeType = fileProperties["mimeType"]

			fileExtension = fileProperties.get("fileExtension")
			metaData = fileProperties.get("videoMediaMetadata")
			parentFolderID = fileProperties.get("parents")

			if not parentFolderID:
				# file not inside a folder
				continue

			parentFolderID = parentFolderID[0]

			if fileProperties["trashed"]:
				deleted = self.syncDeletions(cachedDirectories, cachedFiles, strmRoot, fileID, parentFolderID)
			else:

				if mimeType == "application/vnd.google-apps.folder":
					self.syncFolderChanges(cachedDirectories, cachedFiles, folders, strmRoot, fileID, filename, parentFolderID, driveID)
				else:
					self.syncFileChanges(cachedDirectories, cachedFiles, folders, strmRoot, fileID, filename, mimeType, parentFolderID, fileExtension, newFiles, metaData, driveID)

		if newFiles:

			for folderID, folderInfo in newFiles.items():
				folderSettings = folders[folderID]
				remotePath = folderInfo["remote_path"]
				parentFolderID = folderInfo["parent_folder_id"]
				files = folderInfo["files"]
				self.fileProcessor(cachedDirectories, cachedFiles, files, folderSettings, remotePath, strmRoot, driveID, parentFolderID)

			xbmc.executebuiltin("UpdateLibrary(video,{})".format(strmRoot))

		if deleted:

			if os.name == "nt":
				strmRoot = strmRoot.replace("\\", "\\\\")

			xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.Clean", "params": {"showdialogs": false, "content": "video", "directory": "%s"}}' % strmRoot)

		driveSettings["page_token"] = pageToken
		self.saveStrmSettings()

	def syncDeletions(self, cachedDirectories, cachedFiles, strmRoot, fileID, parentFolderID):

		if fileID in cachedFiles:
			cachedFile, cachedOriginalFilename, cachedParentFolderID, mode, folderStructure = cachedFiles[fileID]

			if folderStructure == "original":
				self.deleteFile(strmRoot, dirPath=cachedDirectories[parentFolderID][0], filename=cachedFile)
			else:
				self.deleteFile(strmRoot, filePath=cachedFile)

			del cachedFiles[fileID]
			cachedDirPath, cachedRootFolderID, cachedParentFolderID, folderIDs, fileIDs = cachedDirectories[cachedParentFolderID]

			if fileID in fileIDs:
				fileIDs.remove(fileID)

			return True

	@staticmethod
	def removeFolderIDfromCachedList(cachedDirectories, parentFolderID, folderID):

		if parentFolderID in cachedDirectories:
			cachedDirPath, cachedRootFolderID, cachedParentFolderID, folderIDs, fileIDs = cachedDirectories[parentFolderID]

			if folderID in folderIDs:
				folderIDs.remove(folderID)

	@staticmethod
	def addFolderIDtoCachedList(cachedDirectories, parentFolderID, folderID):

		if parentFolderID in cachedDirectories:
			cachedDirPath, cachedRootFolderID, cachedParentFolderID, folderIDs, fileIDs = cachedDirectories[parentFolderID]

			if folderID not in folderIDs:
				folderIDs.append(folderID)

	@staticmethod
	def removeFileIDfromCachedList(cachedDirectories, parentFolderID, fileID):

		if parentFolderID in cachedDirectories:
			cachedDirPath, cachedRootFolderID, cachedParentFolderID, folderIDs, fileIDs = cachedDirectories[parentFolderID]

			if fileID in fileIDs:
				fileIDs.remove(fileID)

	@staticmethod
	def addFileIDtoCachedList(cachedDirectories, parentFolderID, fileID):

		if parentFolderID in cachedDirectories:
			cachedDirPath, cachedRootFolderID, cachedParentFolderID, folderIDs, fileIDs = cachedDirectories[parentFolderID]

			if fileID not in fileIDs:
				fileIDs.append(fileID)

	def downloadFolder(self, strmRoot, dirPath, folders, cachedDirectories, cachedFiles, parentFolderID, folderID, rootFolderID, driveID):
		self.addFolderIDtoCachedList(cachedDirectories, parentFolderID, folderID)
		folderSettings = folders[rootFolderID]
		folderRoot = folderSettings["root_path"]
		encrypted = folderSettings["contains_encrypted"]
		dirTree = self.getGDriveFiles(folderID, parentFolderID, dirPath, {}, encrypted)

		for subFolderID, folderInfo in dirTree.items():
			remotePath = folderInfo["remote_path"]
			parentFolderID = folderInfo["parent_folder_id"]
			files = folderInfo["files"]

			dirPath = os.path.join(folderRoot, remotePath)
			cachedDirectories[subFolderID] = [dirPath, rootFolderID, parentFolderID, folderInfo["dirs"], []]
			self.fileProcessor(cachedDirectories, cachedFiles, files, folderSettings, dirPath, strmRoot, driveID, subFolderID)

	def syncFolderChanges(self, cachedDirectories, cachedFiles, folders, strmRoot, folderID, folderName, parentFolderID, driveID):

		if folderID not in cachedDirectories:
			# New folder added
			dirPath, rootFolderID = self.getDirectory(cachedDirectories, folderID)

			if not rootFolderID:
				return

			if os.path.exists(dirPath):
				dirPath = os.path.join(dirPath, folderName)
			else:
				folderID = parentFolderID
				cachedDirPath, cachedRootFolderID, cachedParentFolderID, folderIDs, fileIDs = cachedDirectories[folderID]
				parentFolderID = cachedParentFolderID

			self.downloadFolder(strmRoot, dirPath, folders, cachedDirectories, cachedFiles, parentFolderID, folderID, rootFolderID, driveID)

		else:
			cachedDirPath, cachedRootFolderID, cachedParentFolderID, folderIDs, fileIDs = cachedDirectories[folderID]
			cachedDirPathHead, dirName = cachedDirPath.rsplit(os.sep, 1)

			if not os.path.exists(cachedDirPath):
				copy = cachedDirectories.copy()
				del copy[folderID]
				dirPath, rootFolderID = self.getDirectory(copy, folderID)
				self.deleteFiles(strmRoot, folderID, cachedDirectories, cachedFiles)
				self.removeFolderIDfromCachedList(cachedDirectories, cachedParentFolderID, folderID)

				if not rootFolderID:
					return

				dirPath = os.path.join(dirPath, folderName)
				self.downloadFolder(strmRoot, dirPath, folders, cachedDirectories, cachedFiles, parentFolderID, folderID, cachedRootFolderID, driveID)

			elif parentFolderID != cachedParentFolderID and folderID != cachedRootFolderID:
				copy = cachedDirectories.copy()
				del copy[folderID]
				# folder has been moved into another directory
				dirPath, rootFolderID = self.getDirectory(copy, folderID)

				if dirPath:
					newDirPath = os.path.join(dirPath, folderName)
					self.renameFolder(strmRoot, cachedDirPath, newDirPath)
					cachedDirectories[folderID] = [newDirPath, rootFolderID, parentFolderID, folderIDs, fileIDs]
					self.removeFolderIDfromCachedList(cachedDirectories, cachedParentFolderID, folderID)
					self.addFolderIDtoCachedList(cachedDirectories, parentFolderID, folderID)
				else:
					# folder moved to another root folder != existing root folder - delete current folder
					self.deleteFiles(strmRoot, folderID, cachedDirectories, cachedFiles)
					self.removeFolderIDfromCachedList(cachedDirectories, cachedParentFolderID, folderID)

			elif dirName != folderName:
				# folder name has been changed
				newDirPath = os.path.join(cachedDirPathHead, folderName)
				self.renameFolder(strmRoot, cachedDirPath, newDirPath)
				cachedDirectories[folderID][0] = newDirPath

	def syncFileChanges(self, cachedDirectories, cachedFiles, folders, strmRoot, fileID, filename, mimeType, parentFolderID, fileExtension, newFiles, metaData, driveID):

		if parentFolderID not in cachedDirectories:
			dirPath, rootFolderID = self.getDirectory(cachedDirectories, parentFolderID)

			if not rootFolderID:

				if fileID in cachedFiles:
					# file has moved outside of root folder hierarchy/tree
					cachedFile, cachedOriginalFilename, cachedParentFolderID, mode, folderStructure = cachedFiles[fileID]

					if folderStructure == "original":
						cachedFilePath = os.path.join(cachedDirectories[cachedParentFolderID][0], cachedFile)
					else:
						cachedFilePath = cachedFile

					self.deleteFile(strmRoot, filePath=cachedFilePath)
					del cachedFiles[fileID]
					self.removeFileIDfromCachedList(cachedDirectories, cachedParentFolderID, fileID)

				return

		else:
			dirPath, rootFolderID, cachedParentFolderID, folderIDs, fileIDs = cachedDirectories[parentFolderID]

		folderSettings = folders[rootFolderID]
		encrypted = folderSettings["contains_encrypted"]

		if encrypted and mimeType == "application/octet-stream" and not fileExtension:
			self.loadEncryption()
			filename = self.decryptFilename(filename)

			if not filename:
				return

			fileExtension = filename.rsplit(".", 1)[-1]
			encryptedFile = True
		else:
			encryptedFile = False

		fileType = self.identifyFile(filename, fileExtension, mimeType)
		metadataRefresh = False

		if not fileType:
			return

		if fileID in cachedFiles:
			cachedFile, cachedOriginalFilename, cachedParentFolderID, mode, folderStructure = cachedFiles[fileID]
			cachedDirPath, rootFolderID, _, folderIDs, fileIDs = cachedDirectories[cachedParentFolderID]

			if folderStructure == "original":
				cachedFilePath = os.path.join(cachedDirPath, cachedFile)
			else:
				cachedFilePath = cachedFile

			if cachedOriginalFilename == filename and cachedDirPath == dirPath:
				# this needs to be done as GDRIVE creates multiple changes for a file, one before its metadata is processed and another change after the metadata is processed
				self.deleteFile(strmRoot, filePath=cachedFilePath)
				del cachedFiles[fileID]
				fileIDs.remove(fileID)
				metadataRefresh = True
			else:

				if mode == "rename&delete":

					if not os.path.exists(cachedFilePath):
						self.removeFileIDfromCachedList(cachedDirectories, cachedParentFolderID, fileID)
						del cachedFiles[fileID]
					elif folderStructure == "original":
						fileExtension = os.path.splitext(cachedFile)[1]
						filenameWithoutExt = os.path.splitext(filename)[0]
						newFilename = filenameWithoutExt + fileExtension

						newFilePath = self.renameFile(strmRoot, cachedFilePath, dirPath, newFilename)
						cachedFiles[fileID] = [newFilename, filename, parentFolderID, mode, folderStructure]
						self.removeFileIDfromCachedList(cachedDirectories, cachedParentFolderID, fileID)
						self.addFileIDtoCachedList(cachedDirectories, parentFolderID, fileID)
						return
					elif folderStructure == "modified":
						fileExtension = os.path.splitext(os.path.basename(cachedFile))[1]
						filenameWithoutExt = os.path.splitext(filename)[0]
						newFilename = filenameWithoutExt + fileExtension

						newFilePath = self.renameFile(strmRoot, cachedFilePath, os.path.dirname(cachedFile), newFilename)
						cachedFiles[fileID][0] = newFilePath
						self.removeFileIDfromCachedList(cachedDirectories, cachedParentFolderID, fileID)
						self.addFileIDtoCachedList(cachedDirectories, parentFolderID, fileID)
						return

				else:
					self.deleteFile(strmRoot, filePath=cachedFilePath)
					del cachedFiles[fileID]
					self.removeFileIDfromCachedList(cachedDirectories, cachedParentFolderID, fileID)

		else:

			if not os.path.exists(dirPath):
				folderID = parentFolderID
				parentFolderID = self.cloudService.getDirectory(parentFolderID)[1]
				self.downloadFolder(strmRoot, dirPath, folders, cachedDirectories, cachedFiles, parentFolderID, folderID, rootFolderID, driveID)
				return

		if not newFiles:
			newFiles[rootFolderID] = self.createTreeDic(parentFolderID, dirPath)

		newFiles[rootFolderID]["files"][fileType].append(
			{
				"parent_folder_id": parentFolderID,
				"directory_path": dirPath,
				"filename": filename,
				"id": fileID,
				"metadata": metaData,
				"metadata_refresh": metadataRefresh,
				"encrypted": encryptedFile,
			}
		)
