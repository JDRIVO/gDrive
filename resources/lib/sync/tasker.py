import os
import time
import random
import datetime
import threading
import traceback

import xbmc
import xbmcgui

from . import cache
from .. import sync
from .. import google_api
from .. import encryption
from .. import filesystem


class Tasker:

	def __init__(self, settings, accountManager):
		self.settings = settings
		self.accountManager = accountManager
		self.accounts = self.accountManager.accounts
		self.cloudService = google_api.drive.GoogleDrive()
		self.encrypter = encryption.encrypter.Encrypter(settings=self.settings)
		self.cache = cache.Cache()
		self.fileOperations = filesystem.operations.FileOperations(cloud_service=self.cloudService, encryption=self.encrypter)
		self.fileTree = filesystem.tree.FileTree(self.cloudService, self.cache)
		self.remoteFileProcessor = filesystem.processor.RemoteFileProcessor(self.cloudService, self.fileOperations, self.settings)
		self.localFileProcessor = filesystem.processor.LocalFileProcessor(self.cloudService, self.fileOperations, self.settings)
		self.syncer = sync.syncer.Syncer(self.accountManager, self.cloudService, self.encrypter, self.fileOperations, self.remoteFileProcessor, self.localFileProcessor, self.fileTree, self.settings)
		self.monitor = xbmc.Monitor()
		self.dialog = xbmcgui.Dialog()
		self.taskLock = threading.Lock()
		self.idLock = threading.Lock()
		self.tasks = {}
		self.ids, self.activeTasks = [], []

	def run(self):
		drives = self.cache.getDrives()

		if not drives:
			return

		for driveSettings in drives:
			self.spawnTask(driveSettings)

	@staticmethod
	def strptime(dateString, format):
		return datetime.datetime(*(time.strptime(dateString, format)[:6]))

	@staticmethod
	def floorDT(dt, interval):
		replace = (dt.minute // interval)*interval
		return dt.replace(minute = replace, second=0, microsecond=0)

	def syncAll(self):
		drives = self.cache.getDrives()

		if not drives:
			return

		for driveSettings in drives:
			self.sync(driveSettings["drive_id"])

	def sync(self, driveID):
		self.activeTasks.append(driveID)

		try:

			with self.taskLock:
				self.syncer.syncChanges(driveID)

		except Exception as e:
			xbmc.log(f"gdrive error: {e}: {''.join(traceback.format_tb(e.__traceback__))}", xbmc.LOGERROR)

		self.activeTasks.remove(driveID)

	def createTaskID(self):

		with self.idLock:
			id = random.random()

			while id in self.ids:
				id = random.random()

			self.ids.append(id)
			return id

	def removeTask(self, driveID):

		if driveID in self.tasks:
			del self.tasks[driveID]
			time.sleep(2)

			while driveID in self.activeTasks:
				time.sleep(0.1)

	def spawnTask(self, driveSettings, startUpRun=True):
		driveID = driveSettings["drive_id"]
		taskMode = driveSettings["task_mode"]
		taskFrequency = driveSettings["task_frequency"]
		startupSync = driveSettings["startup_sync"]
		taskID = self.createTaskID()
		self.tasks[driveID] = taskID

		if taskMode == "schedule":
			taskFrequency = self.strptime(taskFrequency.lstrip(), "%H:%M").time()
			threading.Thread(target=self.startScheduledTask, args=(startupSync, taskFrequency, driveID, taskID, startUpRun)).start()
		else:
			taskFrequency = int(taskFrequency) * 60
			threading.Thread(target=self.startIntervalTask, args=(startupSync, taskFrequency, driveID, taskID, startUpRun)).start()

	def startIntervalTask(self, startupSync, taskFrequency, driveID, taskID, startUpRun=True):
		lastUpdate = time.time()

		while not self.monitor.abortRequested():

			if self.tasks.get(driveID) != taskID:
				self.ids.remove(taskID)
				return

			if not startupSync and startUpRun:
				startUpRun = False
				continue

			if time.time() - lastUpdate < taskFrequency and not startUpRun:

				if self.monitor.waitForAbort(1):
					break

				continue

			startUpRun = False
			self.sync(driveID)
			lastUpdate = time.time()

	def startScheduledTask(self, startupSync, taskFrequency, driveID, taskID, startUpRun=True):

		while not self.monitor.abortRequested():

			if self.tasks.get(driveID) != taskID:
				self.ids.remove(taskID)
				return

			if not startupSync and startUpRun:
				startUpRun = False
				continue

			currentTime = self.floorDT(datetime.datetime.now().time(), 1)

			if currentTime != taskFrequency and not startUpRun:

				if self.monitor.waitForAbort(1):
					break

				continue

			startUpRun = False
			self.sync(driveID)

	def createTask(self, driveID, folderID, folderName):
		self.encrypter.setup(settings=self.settings)
		self.accountManager.loadAccounts()
		self.accounts = self.accountManager.accounts
		syncRootPath = self.cache.getSyncRootPath()

		if not os.path.exists(syncRootPath):
			self.fileOperations.createDirs(syncRootPath)

		account = self.accountManager.getAccount(driveID)
		self.cloudService.setAccount(account)
		self.cloudService.refreshToken()

		driveSettings = self.cache.getDrive(driveID)
		folderSettings = self.cache.getFolder(folderID)

		with self.taskLock:
			self.syncer.syncFolderAdditions(syncRootPath, driveSettings["local_path"], folderName, folderSettings, folderID, folderID, folderID, driveID, initialSync=True)

		if not driveSettings["page_token"]:
			self.cache.updateDrive({"page_token": self.cloudService.getPageToken()}, driveID)

		if self.settings.getSetting("update_library"):
			xbmc.executebuiltin(f"UpdateLibrary(video,{syncRootPath})")

		self.dialog.notification(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30044))
		self.spawnTask(driveSettings, startUpRun=False)
