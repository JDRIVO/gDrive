import os
import json
import time
import datetime
from threading import Thread

import xbmc
import xbmcgui
import xbmcvfs

from . import gdrive_api
from .file_operations import FileOperations
from .strm_utils import StrmUtils
from .sync import Sync


class StrmManager(FileOperations, StrmUtils, Sync):

	def __init__(self, settings, accountManager):
		super(StrmManager, self).__init__()
		self.settings = settings
		self.accountManager = accountManager
		self.accounts = self.accountManager.accounts
		self.cloudService = gdrive_api.GoogleDrive(self.accountManager)

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
			self.syncChanges(driveID)
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
			self.syncChanges(driveID)

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
				"files": {},
				"directories": {},
				"root_path": os.path.join(gdriveRoot, driveID),
				"task_details": taskDetails,
			}
			driveSettings = self.strmSettings["drives"][driveID]

		else:
			taskDetails = driveSettings["task_details"]

		encrypted = self.dialog.yesno("gDrive", "Does this folder contain gDrive encrypted files/strms?")

		if encrypted:
			self.loadEncryption()

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
			"folder_structure": folderStructure,
			"file_renaming": fileRenaming,
			"sync_artwork": syncArtwork,
			"sync_nfo": syncNFOs,
			"sync_subtitles": syncSubtitles,
			"root_path": os.path.join(gdriveRoot, driveID, folderName),
			"contains_encrypted": encrypted,
		}

		self.cloudService = gdrive_api.GoogleDrive(self.accountManager)
		account = self.accountManager.getAccount(driveID)
		self.cloudService.setAccount(account)
		self.cloudService.refreshToken()

		strmRoot = self.strmSettings["root_path"]
		folderSettings = driveSettings["folders"][folderID]
		folderRoot = folderSettings["root_path"]
		folders = self.getGDriveFiles(folderID, folderID, folderRoot, {}, encrypted)

		cachedDirectories = driveSettings["directories"]
		cachedFiles = driveSettings["files"]

		for subFolderID, folderInfo in folders.items():
			remotePath = folderInfo["remote_path"]
			parentFolderID = folderInfo["parent_folder_id"]
			dirPath = os.path.join(folderRoot, remotePath)
			cachedDirectories[subFolderID] = [dirPath, folderID, parentFolderID, folderInfo["dirs"], []]
			self.fileProcessor(cachedDirectories, cachedFiles, folderInfo["files"], folderSettings, dirPath, strmRoot, driveID, subFolderID)

		if not driveSettings.get("page_token"):
			driveSettings["page_token"] = self.cloudService.getPageToken()

		self.saveStrmSettings()
		xbmc.executebuiltin("UpdateLibrary(video,{})".format(strmRoot))
		xbmc.executebuiltin("Container.Refresh")
		self.dialog.notification("gDrive", "Sync Completed")
		self.spawnTask(taskDetails, driveID, startUpRun=False)
