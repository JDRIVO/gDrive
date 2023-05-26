import os

import xbmcvfs
import xbmcaddon

from ..ui import dialogs
from constants import settings
from ..filesystem import operations
from ..database.database import Database

ADDON_PATH = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("profile"))

if not os.path.exists(ADDON_PATH):
	os.mkdir(ADDON_PATH)

CACHE_PATH = os.path.join(ADDON_PATH, "cache.db")


class Cache(Database):

	def __init__(self):
		newDB = not os.path.exists(CACHE_PATH)
		super().__init__(CACHE_PATH)
		self.fileOperations = operations.FileOperations()

		if newDB:
			self.createTables()

	def updateDrive(self, data, driveID):
		self.update("drives", data, f"drive_id='{driveID}'")

	def updateFile(self, data, fileID):
		self.update("files", data, f"file_id='{fileID}'")

	def updateFolder(self, data, folderID):
		self.update("folders", data, f"folder_id='{folderID}'")

	def updateDirectory(self, data, folderID):
		self.update("directories", data, f"folder_id='{folderID}'")

	def getDriveSetting(self, column, driveID):
		self.selectConditional("drives", column, f"drive_id='{driveID}'")

	def addDrive(self, data):
		self.insert("drives", data)

	def addFolder(self, data):
		self.insert("folders", data)

	def addDirectory(self, data):
		self.insert("directories", data)

	def addDirectories(self, values):
		columns = (
			"drive_id",
			"folder_id",
			"local_path",
			"parent_folder_id",
			"root_folder_id",
		)
		self.insertMany("directories", columns, values)

	def addFile(self, data):
		self.insert("files", data)

	def addFiles(self, values):
		columns = (
			"drive_id",
			"root_folder_id",
			"parent_folder_id",
			"file_id",
			"local_path",
			"local_name",
			"remote_name",
			"original_name",
			"original_folder",
		)
		self.insertMany("files", columns, values)

	def getDrives(self):
		drives = self.selectAll("drives")
		return drives

	def getDrive(self, value, column="drive_id"):
		drive = self.selectAllConditional("drives", f"{column}='{value}'")
		if drive: return drive[0]

	def getDirectory(self, value, column="folder_id"):
		directory = self.selectAllConditional("directories", f"{column}='{value}'")
		if directory: return directory[0]

	def getFolder(self, value, column="folder_id"):
		folder = self.selectAllConditional("folders", f"{column}='{value}'")
		if folder: return folder[0]

	def getFile(self, value, column="file_id"):
		file = self.selectAllConditional("files", f"{column}='{value}'")
		if file: return file[0]

	def getFolders(self, value, column="drive_id"):
		return self.selectAllConditional("folders", f"{column}='{value}'")

	def getDirectories(self, value, column="parent_folder_id"):
		return self.selectAllConditional("directories", f"{column}='{value}'")

	def getFiles(self, value, column="parent_folder_id"):
		return self.selectAllConditional("files", f"{column}='{value}'")

	def deleteFile(self, value, column="file_id"):
		self.delete("files", f"{column}='{value}'")

	def deleteDirectory(self, value, column="folder_id"):
		self.delete("directories", f"{column}='{value}'")

	def deleteFolder(self, value, column="folder_id"):
		self.delete("folders", f"{column}='{value}'")

	# def deleteDrive(self, driveID):
		# syncRootPath = self.getSyncRootPath()
		# drive = self.getDrive(driveID)

		# if not drive:
			# return

		# drivePath = os.path.join(syncRootPath, drive["local_path"])
		# files = self.getFiles(driveID, "drive_id")
		# directories = {d["folder_id"]: d for d in self.getDirectories(driveID, "drive_id")}

		# for file in files:

			# if file["original_folder"]:
				# parentFolderID = file["parent_folder_id"]
				# filePath = os.path.join(syncRootPath, drivePath, directories[parentFolderID]["local_path"], file["local_name"])
			# else:
				# filePath = os.path.join(syncRootPath, file["local_path"])

			# self.fileOperations.deleteFile(syncRootPath, filePath=filePath)

		# self.deleteFile(driveID, "drive_id")
		# self.deleteFolder(driveID, "drive_id")
		# self.deleteDirectory(driveID, "drive_id")
		# self.delete("drives", f"drive_id='{driveID}'")

	def deleteDrive(self, driveID):
		drive = self.getDrive(driveID)

		if not drive:
			return

		self.deleteFolder(driveID, "drive_id")
		self.delete("drives", f"drive_id='{driveID}'")
		syncRootPath = self.getSyncRootPath()
		drivePath = os.path.join(syncRootPath, drive["local_path"])
		self.cleanCache(syncRootPath, drivePath, driveID, column="drive_id", pDialog=settings.getSetting("file_deletion_dialog"))

	def removeFolder(self, folderID, deleteFiles=False):
		folder = self.getFolder(folderID)
		self.deleteFolder(folderID)
		driveID = folder["drive_id"]
		drive = self.getDrive(driveID)
		syncRootPath = self.getSyncRootPath()
		drivePath = os.path.join(syncRootPath, drive["local_path"])
		self.cleanCache(syncRootPath, drivePath, folderID, deleteFiles=deleteFiles, pDialog=settings.getSetting("file_deletion_dialog"))

	def removeAllFolders(self, driveID, deleteFiles=False):
		folders = self.getFolders(driveID)
		self.deleteFolder(driveID, column="drive_id")
		drive = self.getDrive(driveID)
		syncRootPath = self.getSyncRootPath()
		drivePath = os.path.join(syncRootPath, drive["local_path"])

		for folder in folders:
			self.cleanCache(syncRootPath, drivePath, folder["folder_id"], deleteFiles=deleteFiles, pDialog=settings.getSetting("file_deletion_dialog"))

	def updateSyncRootPath(self, path):
		self.update("global", {"local_path": path}, "local_path=TEXT")

	def setSyncRootPath(self, path):
		self.insert("global", {"local_path": path})

	def getSyncRootPath(self):
		return self.select("global", "local_path")

	def addGlobalData(self, data):
		self.insert("global", data)

	def updateChildPaths(self, oldPath, newPath, folderID):
		directories = self.getDirectories(folderID, "folder_id")
		processedIDs = set()

		while directories:
			directory = directories.pop()
			folderID = directory["folder_id"]
			directory["local_path"] = directory["local_path"].replace(oldPath, newPath, 1)
			self.updateDirectory(directory, folderID)

			if folderID in processedIDs:
				continue

			processedIDs.add(folderID)
			directories += self.getDirectories(folderID, "parent_folder_id")

	def cleanCache(self, syncRootPath, drivePath, folderID, column="folder_id", deleteFiles=True, pDialog=False):
		directories = self.getDirectories(folderID, column)

		if deleteFiles and pDialog:
			pDialog = dialogs.FileDeletionDialog(0, heading=settings.getLocalizedString(30075))

		while directories:
			directory = directories.pop()
			folderID = directory["folder_id"]
			files = self.getFiles(folderID)

			if deleteFiles:

				if pDialog:
					pDialog.fileCount += len(files)

				for file in files:

					if file["original_folder"]:
						filename = file["local_name"]
						filePath = os.path.join(os.path.join(drivePath, directory["local_path"]), filename)
					else:
						filePath = os.path.join(syncRootPath, file["local_path"])
						filename = os.path.basename(filePath)

					self.fileOperations.deleteFile(syncRootPath, filePath=filePath)

					if pDialog:
						pDialog.update(filename)

			self.deleteFile(folderID, "parent_folder_id")
			self.deleteDirectory(folderID)
			directories += self.getDirectories(folderID, "parent_folder_id")

		if pDialog:
			pDialog.close()

	def createGlobalTable(self):
		columns = [
			"local_path TEXT",
			"operating_system TEXT",
		]
		self.createTable("global", columns)

	def createDriveTable(self):
		columns = [
			"drive_id TEXT",
			"local_path TEXT",
			"page_token INTEGER",
			"last_update REAL",
			"task_mode TEXT",
			"task_frequency TEXT",
			"startup_sync INTEGER",
		]
		self.createTable("drives", columns)

	def createFoldersTable(self):
		columns = [
			"drive_id TEXT",
			"folder_id TEXT",
			"local_path TEXT",
			"remote_name TEXT",
			"file_renaming INTEGER",
			"folder_restructure INTEGER",
			"contains_encrypted INTEGER",
			"sync_artwork INTEGER",
			"sync_nfo INTEGER",
			"sync_subtitles INTEGER",
			"tmdb_language TEXT",
			"tmdb_region TEXT",
			"tmdb_adult TEXT",
		]
		self.createTable("folders", columns)

	def createDirectoriesTable(self):
		columns = [
			"drive_id TEXT",
			"root_folder_id TEXT",
			"parent_folder_id TEXT",
			"folder_id TEXT",
			"local_path TEXT",
			"remote_name TEXT",
		]
		self.createTable("directories", columns)

	def createFilesTable(self):
		columns = [
			"drive_id TEXT",
			"root_folder_id TEXT",
			"parent_folder_id TEXT",
			"file_id TEXT",
			"local_path TEXT",
			"local_name TEXT",
			"remote_name TEXT",
			"original_name INTEGER",
			"original_folder INTEGER",
		]
		self.createTable("files", columns)

	def createTables(self):
		self.createGlobalTable()
		self.createDriveTable()
		self.createFoldersTable()
		self.createDirectoriesTable()
		self.createFilesTable()
