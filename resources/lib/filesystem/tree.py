import os
import threading

from . import helpers
from .constants import *
from .folder import Folder
from ..threadpool import threadpool


class FileTree:

	def __init__(self, cloudService, cache):
		self.cloudService = cloudService
		self.cache = cache
		self.counterLock = threading.Lock()

	def buildTree(self, folderID, parentFolderID, path, excludedTypes, encrypter, syncedIDs, excludedIDs, threadCount):
		self.fileCount = 0
		fileTree = dict()
		remoteName = os.path.basename(path)
		path_ = path
		copy = 1

		while self.cache.getDirectory(path, column="local_path"):
			path = f"{path_} ({copy})"
			copy += 1

		fileTree[folderID] = Folder(folderID, parentFolderID, remoteName, path)
		yield from self.getContents(fileTree, [folderID], excludedTypes, encrypter, syncedIDs, excludedIDs, threadCount)

	def getContents(self, fileTree, folderIDs, excludedTypes, encrypter, syncedIDs, excludedIDs, threadCount):
		maxIDs = 299
		queries = []

		while folderIDs:
			ids = folderIDs[:maxIDs]
			queries.append(
				(
					"not trashed and (" + " or ".join(f"'{id}' in parents" for id in ids) + ")",
					ids,
				)
			)
			folderIDs = folderIDs[maxIDs:]

		with threadpool.ThreadPool(threadCount) as pool:

			for query, parentFolderIDs in queries:
				items = self.cloudService.listDirectory(customQuery=query)
				yield from self.filterContents(fileTree, items, parentFolderIDs, folderIDs, excludedTypes, encrypter, syncedIDs, excludedIDs)

		if folderIDs:
			yield from self.getContents(fileTree, folderIDs, excludedTypes, encrypter, syncedIDs, excludedIDs, threadCount)

	def filterContents(self, fileTree, items, parentFolderIDs, folderIDs, excludedTypes, encrypter, syncedIDs, excludedIDs):
		paths = []

		for item in items:
			id = item["id"]

			if id in excludedIDs:
				continue

			if syncedIDs is not None:
				syncedIDs.append(id)

			parentFolderID = item["parents"][0]
			mimeType = item["mimeType"]

			if mimeType == "application/vnd.google-apps.folder":
				folderName = item["name"]
				path = path_ = os.path.join(fileTree[parentFolderID].path, helpers.removeProhibitedFSchars(folderName))
				copy = 1

				while path in paths:
					path = f"{path_} ({copy})"
					copy += 1

				paths.append(path)
				fileTree[id] = Folder(id, parentFolderID, folderName, path)
				folderIDs.append(id)
				continue

			file = helpers.makeFile(item, excludedTypes, encrypter)

			if not file:
				continue

			with self.counterLock:
				self.fileCount += 1

			files = fileTree[parentFolderID].files

			if file.type in MEDIA_ASSETS:
				mediaAssets = files["media_assets"]

				if file.ptnName not in mediaAssets:
					mediaAssets[file.ptnName] = []

				mediaAssets[file.ptnName].append(file)
			else:
				files[file.type].append(file)

		for id in parentFolderIDs:
			yield fileTree[id]
