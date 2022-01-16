import os
import sys
import glob
import json
import time
import urllib
import datetime

import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import xbmcplugin

import constants
from . import account_manager, gdrive_api, strm_manager


class ContentEngine:

	def __init__(self):
		self.pluginHandle = int(sys.argv[1])
		self.settings = constants.settings
		self.accountManager = account_manager.AccountManager(self.settings)
		self.accounts = self.accountManager.accounts
		self.cloudService = gdrive_api.GoogleDrive(self.accountManager)

	def run(self, dbID, dbType, filePath):
		mode = self.settings.getParameter("mode", "main").lower()
		pluginQueries = self.settings.parseQuery(sys.argv[2][1:])
		self.dialog = xbmcgui.Dialog()

		# Temp - to be deleted in the future
		if not self.settings.getSetting("accounts_converted"):
			self.convertAccounts()

		modes = {
			"main": self.createMainMenu,
			"enroll_account": self.enrollAccount,
			"add_service_account": self.addServiceAccount,
			"validate_accounts": self.validateAccounts,
			"delete_accounts": self.accountDeletion,
			"list_accounts": self.createDriveMenu,
			"list_directory": self.listDirectory,
			"add_strm": self.addStrm,
			"video": self.playVideo,
			"resolution_priority": self.resolutionPriority,
			"not_implemented": self.notImplemented,
			"accounts_cm": self.accountsContextMenu,
		}

		if mode == "video":
			modes[mode](dbID, dbType, filePath)
		else:
			modes[mode]()

		xbmcplugin.endOfDirectory(self.pluginHandle)

	def accountsContextMenu(self):
		options = [
			self.settings.getLocalizedString(30002),
			self.settings.getLocalizedString(30023),
			self.settings.getLocalizedString(30159),
		]
		driveID = self.settings.getParameter("drive_id")
		accountName = self.settings.getParameter("account_name")
		accountIndex = int(self.settings.getParameter("account_index"))
		selection = self.dialog.contextmenu(options)
		account = self.accounts[driveID][accountIndex]

		if selection == 0:
			newAccountName = self.dialog.input(self.settings.getLocalizedString(30002) + ": " + accountName)

			if not newAccountName:
				return

			self.accountManager.renameAccount(driveID, accountIndex, newAccountName)

		elif selection == 1:
			self.cloudService.setAccount(account)
			validation = self.cloudService.refreshToken()

			if validation == "failed":
				selection = self.dialog.yesno(
					self.settings.getLocalizedString(30000),
					"{} {}".format(accountName, self.settings.getLocalizedString(30019)),
				)

				if not selection:
					return

				self.accountManager.deleteAccount(driveID, account)

			else:
				self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30020))
				return

		elif selection == 2:
			selection = self.dialog.yesno(
				self.settings.getLocalizedString(30000),
				"{} {}?".format(
					self.settings.getLocalizedString(30121),
					accountName,
				)
			)

			if not selection:
				return

			self.accountManager.deleteAccount(driveID, account)

		else:
			return

		xbmc.executebuiltin("Container.Refresh")

	def refreshAccess(self, expiry):
		accessExpiry = datetime.datetime(*(time.strptime(expiry, "%Y-%m-%d %H:%M:%S.%f")[0:6]))
		timeNow = datetime.datetime.now()

		if timeNow >= accessExpiry:
			self.cloudService.refreshToken()
			self.accountManager.saveAccounts()

	def convertAccounts(self):

		if self.accounts:

			try:
				int(self.accounts.keys()[0])
			except:
				pass

			accounts = {}

			for account, accountInfo in self.accounts.items():
				self.cloudService.setAccount(accountInfo)
				self.cloudService.refreshToken()
				driveID = self.cloudService.getDriveID()
				driveAccounts = accounts.get(driveID)

				if driveAccounts:
					driveAccounts.append(accountInfo)
				else:
					accounts[driveID] = [accountInfo]

			self.accountManager.accounts = accounts
			self.accountManager.saveAccounts()

		self.settings.setSetting("accounts_converted", "true")
		xbmc.executebuiltin("Container.Refresh")

	def notImplemented(self):
		self.dialog.notification("gDrive", "Not implemented")

	def addMenu(self, url, title, cm=False, folder=True):
		listitem = xbmcgui.ListItem(title)

		if cm:
			listitem.addContextMenuItems(cm, True)

		xbmcplugin.addDirectoryItem(self.pluginHandle, url, listitem, isFolder=folder)

	def createMainMenu(self):
		pluginURL = sys.argv[0]
		strmInfo = self.getStrmSettings()
		num = 1

		if strmInfo:
			self.addMenu(
				strmInfo["root_path"],
				"[B]1. Browse STRM[/B]",
				folder=True,
			)
			num += 1

		self.addMenu(
			pluginURL + "?mode=enroll_account",
			"[B]{}. {}[/B]".format(num, self.settings.getLocalizedString(30207)),
			folder=False,
		)
		contextMenu = [
			(
				"Create alias",
				"RunPlugin({})".format(pluginURL + "?mode=not_implemented")
			)
		]

		for driveID in self.accounts:
			self.addMenu(
				"{}?mode=list_accounts&drive_id={}".format(pluginURL, driveID),
				"DRIVE: " + driveID,
				cm=contextMenu,
			)

		xbmcplugin.setContent(self.pluginHandle, "files")
		# xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_FILE)
		# xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_FOLDERS)
		xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_FOLDERS)

	def createDriveMenu(self):
		pluginURL = sys.argv[0]
		driveID = self.settings.getParameter("drive_id")
		account = self.accountManager.getAccount(driveID)

		if not account:
			return

		self.cloudService.setAccount(account)
		self.refreshAccess(account["expiry"])
		strmSettings = self.getStrmSettings()

		if strmSettings:
			driveSettings = strmSettings["drives"].get(driveID)
		else:
			driveSettings = False

		self.addMenu(
			"{}?mode=add_service_account&drive_id={}".format(pluginURL, driveID),
			"[B]1. {}[/B]".format(self.settings.getLocalizedString(30214)),
			folder=False,
		)
		num = 2

		if driveSettings:
			self.addMenu(
				pluginURL + "?mode=not_implemented",
				"[B]{}. Sync Settings / Force Sync[/B]".format(num),
				folder=False,
			)
			num += 1

		self.addMenu(
			"{}?mode=validate_accounts&drive_id={}".format(pluginURL, driveID),
			"[B]{}. {}[/B]".format(num, self.settings.getLocalizedString(30021)),
			folder=False,
		)
		num += 1
		self.addMenu(
			"{}?mode=delete_accounts&drive_id={}".format(pluginURL, driveID),
			"[B]{}. {}[/B]".format(num, self.settings.getLocalizedString(30022)),
			folder=False,
		)
		self.addMenu(
			"{}?mode=list_directory&drive_id={}".format(pluginURL, driveID),
			"[B]My Drive[/B]",
		)
		self.addMenu(
			"{}?mode=list_directory&drive_id={}&shared_with_me=true".format(pluginURL, driveID),
			"[B]Shared With Me[/B]",
		)

		sharedDrives = self.cloudService.getDrives()

		if sharedDrives:

			for sharedDrive in sharedDrives:
				sharedDriveID = sharedDrive["id"]
				sharedDriveName = sharedDrive["name"]
				self.addMenu(
					"{}?mode=list_directory&drive_id={}&shared_drive_id={}".format(pluginURL, driveID, sharedDriveID),
					"[B]{}[/B]".format(sharedDriveName),
				)

		for index, accountInfo in enumerate(self.accounts[driveID]):
			accountName = accountInfo["username"]
			accountName = "[COLOR deepskyblue][B]{}[/B][/COLOR]".format(accountName)
			self.addMenu(
				"{}?mode=accounts_cm&account_name={}&account_index={}&drive_id={}".format(pluginURL, accountName, index, driveID),
				accountName,
				folder=False,
			)

		xbmcplugin.setContent(self.pluginHandle, "files")
		xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_LABEL)

	def listDirectory(self):
		pluginURL = sys.argv[0]
		driveID = self.settings.getParameter("drive_id")
		sharedDriveID = self.settings.getParameter("shared_drive_id")
		folderID = self.settings.getParameter("folder_id")
		sharedWithMe = self.settings.getParameter("shared_with_me")

		if not folderID:

			if sharedDriveID:
				folderID = sharedDriveID
			else:
				folderID = driveID

		account = self.accountManager.getAccount(driveID)
		self.cloudService.setAccount(account)
		self.refreshAccess(account["expiry"])
		folders = self.cloudService.listDir(folderID=folderID, sharedWithMe=sharedWithMe, foldersOnly=True)
		strmSettings = self.getStrmSettings()

		if strmSettings:
			driveSettings = strmSettings["drives"].get(driveID)
		else:
			driveSettings = False

		for folder in folders:
			folderID = folder["id"]
			folderName = folder["name"]

			if driveSettings:
				folderSettings = driveSettings["folders"].get(folderID)
			else:
				folderSettings = False

			if folderSettings:
				contextMenu = [
					(
						"Folders Sync Settings",
						"RunPlugin({})".format(
							pluginURL + "?mode=not_implemented&drive_id={}&folder_id={}&folder_name={}".format(
								driveID, folderID if folderID else driveID, folderName
							)
						)
					),
					(
						"Stop Folder Sync",
						"RunPlugin({})".format(
							pluginURL + "?mode=not_implemented&drive_id={}&folder_id={}&folder_name={}".format(
								driveID, folderID if folderID else driveID, folderName
							)
						)
					)
				]
				folderName = "[COLOR crimson][B]{}[/B][/COLOR]".format(folderName)
			else:
				contextMenu = [
					(
						"Sync folder",
						"RunPlugin({})".format(
							pluginURL + "?mode=add_strm&drive_id={}&folder_id={}&folder_name={}".format(
							driveID, folderID if folderID else driveID, folderName
							)
						)
					)
				]

			self.addMenu(
				pluginURL + "?mode=list_directory&drive_id={}&folder_id={}".format(driveID, folderID),
				folderName,
				cm=contextMenu,
			)

		xbmcplugin.setContent(self.pluginHandle, "files")
		xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_LABEL)

	def addStrm(self):
		driveID = self.settings.getParameter("drive_id")
		folderID = self.settings.getParameter("folder_id")
		folderName = self.settings.getParameter("folder_name")
		serverPort = self.settings.getSettingInt("server_port", 8011)

		data = "drive_id={}&folder_id={}&folder_name={}".format(driveID, folderID, folderName)
		url = "http://localhost:{}/add_sync_task".format(serverPort)
		req = urllib.request.Request(url, data.encode("utf-8"))
		response = urllib.request.urlopen(req)
		response.close()

	def getStrmSettings(self):
		strm = self.settings.getSetting("strm")

		if strm:
			return json.loads(strm)

	def enrollAccount(self):
		import socket

		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(("8.8.8.8", 80))
		address = s.getsockname()[0]
		s.close()

		selection = self.dialog.ok(
			self.settings.getLocalizedString(30000),
			"{} [B][COLOR blue]http://{}:{}/enroll[/COLOR][/B] {}".format(
				self.settings.getLocalizedString(30210),
				address,
				self.settings.getSetting("server_port"),
				self.settings.getLocalizedString(30218),
			)
		)

		if selection:
			xbmc.executebuiltin("Container.Refresh")

	def addServiceAccount(self):
		accountName = self.dialog.input(self.settings.getLocalizedString(30025))

		if not accountName:
			return

		keyFilePath = self.dialog.browse(1, self.settings.getLocalizedString(30026), "files")

		if not keyFilePath:
			return

		if not keyFilePath.endswith(".json"):
			self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30027))
			return

		with open(keyFilePath, "r") as key:
			keyFile = json.loads(key.read())

		error = []

		try:
			email = keyFile["client_email"]
		except:
			error.append("email")

		try:
			key = keyFile["private_key"]
		except:
			error.append("key")

		if error:

			if len(error) == 2:
				self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30028))
			elif "email" in error:
				self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30029))
			elif "key" in error:
				self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30030))

			return

		account = {
			"username": accountName,
			"email": email,
			"key": key,
			"service": True,
		}
		self.cloudService.setAccount(account)
		outcome = self.cloudService.refreshToken()

		if outcome == "failed":
			return

		driveID = self.settings.getParameter("drive_id")
		self.accountManager.addAccount(account, driveID)
		xbmc.executebuiltin("Container.Refresh")

	def validateAccounts(self):
		driveID = self.settings.getParameter("drive_id")
		accounts = self.accounts[driveID]
		accountAmount = len(accounts)
		pDialog = xbmcgui.DialogProgress()

		pDialog.create(self.settings.getLocalizedString(30306))
		deletion = False
		count = 1

		for accountInfo in list(accounts):
			accountName = accountInfo["username"]

			if pDialog.iscanceled():
				return

			self.cloudService.setAccount(accountInfo)
			validation = self.cloudService.refreshToken()
			pDialog.update(int(round(count / accountAmount * 100)), accountName)
			count += 1

			if validation == "failed":
				selection = self.dialog.yesno(
					self.settings.getLocalizedString(30000),
					"{} {}".format(accountName, self.settings.getLocalizedString(30019)),
				)

				if not selection:
					continue

				accounts.remove(accountInfo)
				deletion = True

		pDialog.close()
		self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30020))

		if deletion:
			xbmc.executebuiltin("Container.Refresh")

	def accountDeletion(self):
		driveID = self.settings.getParameter("drive_id")
		accounts = self.accounts[driveID]
		accountNames = [accountInfo["username"] for accountInfo in accounts]
		selection = self.dialog.multiselect(self.settings.getLocalizedString(30158), accountNames)

		if not selection:
			return

		for account in selection:
			accounts.pop(account)

		self.accountManager.saveAccounts()
		self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30161))
		xbmc.executebuiltin("Container.Refresh")

	def resolutionPriority(self):
		resolutions = self.settings.getSetting("resolution_priority").split(", ")
		resolutionOrder = ResolutionOrder(resolutions=resolutions)

		resolutionOrder.doModal()
		newOrder = resolutionOrder.priorityList
		del resolutionOrder

		if newOrder:
			self.settings.setSetting("resolution_priority", ", ".join(newOrder))

	def playVideo(self, dbID, dbType, filePath):

		if (not dbID or not dbType) and not filePath:
			timeEnd = time.time() + 1

			while time.time() < timeEnd and (not dbID or not dbType):
				xbmc.executebuiltin("Dialog.Close(busydialog)")
				dbID = xbmc.getInfoLabel("ListItem.DBID")
				dbType = xbmc.getInfoLabel("ListItem.DBTYPE")
				filePath = xbmc.getInfoLabel("ListItem.FileNameAndPath")

		resumePosition = 0
		resumeOption = False
		playbackAction = self.settings.getSetting("playback_action")

		if playbackAction != "Play from beginning":

			if dbID:

				if dbType == "movie":
					jsonQuery = xbmc.executeJSONRPC(
						'{"jsonrpc": "2.0", "id": "1", "method": "VideoLibrary.GetMovieDetails", "params": {"movieid": %s, "properties": ["resume"]}}'
						% dbID
					)
					jsonKey = "moviedetails"
				else:
					jsonQuery = xbmc.executeJSONRPC(
						'{"jsonrpc": "2.0", "id": "1", "method": "VideoLibrary.GetEpisodeDetails", "params": {"episodeid": %s, "properties": ["resume"]}}'
						% dbID
					)
					jsonKey = "episodedetails"

				jsonResponse = json.loads(jsonQuery.encode("utf-8"))

				try:
					resumeData = jsonResponse["result"][jsonKey]["resume"]
				except:
					return

				resumePosition = resumeData["position"]
				videoLength = resumeData["total"]

			elif filePath:
				from sqlite3 import dbapi2 as sqlite

				dbPath = xbmcvfs.translatePath(self.settings.getSetting("video_db"))
				db = sqlite.connect(dbPath)
				fileDir = os.path.dirname(filePath) + os.sep
				fileName = os.path.basename(filePath)

				try:
					resumePosition = list(
						db.execute(
							"SELECT timeInSeconds FROM bookmark WHERE idFile=(SELECT idFile FROM files WHERE idPath=(SELECT idPath FROM path WHERE strPath=?) AND strFilename=?)",
							(fileDir, fileName)
						)
					)
				except:
					self.dialog.ok(
						self.settings.getLocalizedString(30000),
						self.settings.getLocalizedString(30221),
					)
					return

				if resumePosition:
					resumePosition = resumePosition[0][0]
					videoLength = list(
						db.execute(
							"SELECT totalTimeInSeconds FROM bookmark WHERE idFile=(SELECT idFile FROM files WHERE idPath=(SELECT idPath FROM path WHERE strPath=?) AND strFilename=?)",
							(fileDir, fileName)
						)
					)[0][0]
				else:
					resumePosition = 0

			# import pickle

			# resumeDBPath = xbmcvfs.translatePath(self.settings.resumeDBPath)
			# resumeDB = os.path.join(resumeDBPath, "kodi_resumeDB.p")

			# try:
				# with open(resumeDB, "rb") as dic:
					# videoData = pickle.load(dic)
			# except:
				# videoData = {}

			# try:
				# resumePosition = videoData[filename]
			# except:
				# videoData[filename] = 0
				# resumePosition = 0

			# strmName = self.settings.getParameter("title") + ".strm"
			# cursor = list(db.execute("SELECT timeInSeconds FROM bookmark WHERE idFile=(SELECT idFile FROM files WHERE strFilename='%s')" % strmName))

			# if cursor:
				# resumePosition = cursor[0][0]
			# else:
				# resumePosition = 0

		if resumePosition > 0:

			if playbackAction == "Show resume prompt":
				options = ("Resume from " + str(time.strftime("%H:%M:%S", time.gmtime(resumePosition))), "Play from beginning")
				selection = self.dialog.contextmenu(options)

				if selection == 0:
					# resumePosition = resumePosition / total * 100
					resumeOption = True
				# elif selection == 1:
					# resumePosition = "0"
					# videoData[filename] = 0
				elif selection == -1:
					return

			else:
				resumeOption = True

		crypto = self.settings.getParameter("encfs")
		fileID = self.settings.getParameter("file_id") # self.settings.getParameter("filename")
		driveID = self.settings.getParameter("drive_id")
		driveURL = self.cloudService.constructDriveURL(fileID)

		account = self.accountManager.getAccount(driveID)
		self.cloudService.setAccount(account)
		self.refreshAccess(account["expiry"])
		transcoded = False

		if crypto:

			if not self.settings.getSetting("crypto_password") or not self.settings.getSetting("crypto_salt"):
				self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30208))
				return

		else:
			qualityPrompty = self.settings.getSetting("quality_prompt")
			resolutionPriority = self.settings.getSetting("resolution_priority").split(", ")

			if qualityPrompty:
				streams = self.cloudService.getStreams(fileID)

				if streams:
					resolutions = ["Original"] + [s[0] for s in streams]
					selection = self.dialog.select(self.settings.getLocalizedString(30031), resolutions)

					if selection == -1:
						return

					if resolutions[selection] != "Original":
						driveURL = streams[selection - 1][1]
						transcoded = resolutions[selection]

			elif resolutionPriority[0] != "Original":
				stream = self.cloudService.getStreams(fileID, resolutionPriority)

				if stream:
					transcoded, driveURL = stream

		self.accountManager.saveAccounts()
		serverPort = self.settings.getSettingInt("server_port", 8011)
		url = "http://localhost:{}/play_url".format(serverPort)
		data = "encrypted={}&url={}&driveid={}&fileid={}&transcoded={}".format(crypto, driveURL, driveID, fileID, transcoded)
		req = urllib.request.Request(url, data.encode("utf-8"))

		try:
			response = urllib.request.urlopen(req)
			response.close()
		except urllib.error.URLError as e:
			xbmc.log("gdrive error: " + str(e))
			return

		item = xbmcgui.ListItem(path="http://localhost:{}/play".format(serverPort))
		# item.setProperty("StartPercent", str(position))
		# item.setProperty("startoffset", "60")

		if resumeOption:
			# item.setProperty("totaltime", "1")
			item.setProperty("totaltime", str(videoLength))
			item.setProperty("resumetime", str(resumePosition))

		if self.settings.getSetting("subtitles") == "Subtitles are named the same as STRM":
			subtitles = glob.glob(glob.escape(filePath.rstrip(".strm")) + "*[!gom]")
			item.setSubtitles(subtitles)
		else:
			subtitles = glob.glob(glob.escape(os.path.dirname(filePath) + os.sep) + "*[!gom]")
			item.setSubtitles(subtitles)

		xbmcplugin.setResolvedUrl(self.pluginHandle, True, item)

		if dbID:
			widget = 0 if xbmc.getInfoLabel("Container.Content") else 1
			data = "dbid={}&dbtype={}&widget={}&track={}".format(dbID, dbType, widget, 1)
		else:
			data = "dbid={}&dbtype={}&widget={}&track={}".format(0, 0, 0, 0)

		url = "http://localhost:{}/start_player".format(serverPort)
		req = urllib.request.Request(url, data.encode("utf-8"))
		response = urllib.request.urlopen(req)
		response.close()

			# with open(resumeDB, "wb+") as dic:
				# pickle.dump(videoData, dic)

			# del videoData

			# with open(resumeDB, "rb") as dic:
				# videoData = pickle.load(dic)

			# if player.videoWatched:
				# del videoData[filename]
			# else:
				# videoData[filename] = player.time

			# with open(resumeDB, "wb+") as dic:
				# pickle.dump(videoData, dic)

		# request = {"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"filter": {"field": "playcount", "operator": "greaterthan", "value": "0"}, "limits": {"start": 0}, "properties": ["playcount"], "sort": {"order": "ascending", "method": "label"}}, "id": "libMovies"}
		# request = {"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": {"filter": {"field": "playcount", "operator": "greaterthan", "value": "0"}, "limits": {"start": 0}, "properties": ["playcount"], "sort": {"order": "ascending", "method": "label"}}, "id": "libMovies"}


class ResolutionOrder(xbmcgui.WindowDialog):
	ACTION_MOVE_LEFT = 1
	ACTION_MOVE_RIGHT = 2
	ACTION_MOVE_UP = 3
	ACTION_MOVE_DOWN = 4
	ACTION_SELECT_ITEM = 7
	ACTION_BACKSPACE = 92

	def __init__(self, *args, **kwargs):
		self.resolutions = kwargs["resolutions"]
		addon = xbmcaddon.Addon()

		mediaPath = os.path.join(addon.getAddonInfo('path'), 'resources', 'media')
		self.blueTexture = os.path.join(mediaPath, "blue.png")
		self.grayTexture = os.path.join(mediaPath, "gray.png")

		self.priorityList = None
		self.shift = False

		viewportWidth = self.getWidth()
		viewportHeight = self.getHeight()

		w = int(350 * viewportWidth / 1920)
		h = int(350 * viewportHeight / 1080)

		self.x = int((viewportWidth - w) / 2)
		self.y = int((viewportHeight - h) / 2)

		background = xbmcgui.ControlImage(self.x, self.y, w, h, os.path.join(mediaPath, "black.png"))
		bar = xbmcgui.ControlImage(self.x, self.y, w, 40, self.blueTexture)
		label = xbmcgui.ControlLabel(self.x + 10, self.y + 5, 0, 0, "Resolution Priority")

		self.addControls([background, bar, label])
		self.createButtons()

	def onAction(self, action):
		action = action.getId()
		self.buttonID = self.getFocusId()

		if action == self.ACTION_BACKSPACE:
			self.close()
		elif action == self.ACTION_MOVE_UP:

			if self.buttonID in self.buttonIDs:
				self.updateList("up")
			else:

				if self.buttonID == self.buttonOKid:
					self.setFocus(self.buttonClose)
				else:
					self.setFocus(self.buttonOK)

		elif action == self.ACTION_MOVE_DOWN:

			if self.buttonID in self.buttonIDs:
				self.updateList("down")
			else:

				if self.buttonID == self.buttonOKid:
					self.setFocus(self.buttonClose)
				else:
					self.setFocus(self.buttonOK)

		elif action in (self.ACTION_MOVE_RIGHT, self.ACTION_MOVE_LEFT):
			self.shift = False

			if self.buttonID in self.buttonIDs:
				self.setFocus(self.buttonOK)
			else:
				self.setFocusId(self.buttonIDs[0])

		elif action == self.ACTION_SELECT_ITEM:

			if not self.shift:
				self.shift = True
			else:
				self.shift = False

	def onControl(self, control):
		self.buttonID = control.getId()

		if self.buttonID == self.buttonCloseID:
			self.close()
		elif self.buttonID == self.buttonOKid:
			self.priorityList = [self.getLabel(button) for button in self.buttonIDs]
			self.close()

	def updateList(self, direction):
		currentIndex = self.buttonIDs.index(self.buttonID)

		if direction == "up":
			newIndex = currentIndex - 1
		elif direction == "down":
			newIndex = currentIndex + 1

			if newIndex == len(self.buttonIDs):
				newIndex = 0

		currentButton = self.getButton(self.buttonIDs[currentIndex])
		newButton = self.getButton(self.buttonIDs[newIndex])

		if self.shift:

			if currentIndex == 0 and direction == "up":
				labels = [self.getLabel(button) for button in self.buttonIDs[1:]] + [self.getLabel(self.buttonIDs[0])]
				[self.getButton(buttonID).setLabel(labels[index]) for index, buttonID in enumerate(self.buttonIDs)]
			elif currentIndex == len(self.buttonIDs) - 1 and direction == "down":
				labels = [self.getLabel(self.buttonIDs[-1])] + [self.getLabel(button) for button in self.buttonIDs[:-1]]
				[self.getButton(buttonID).setLabel(labels[index]) for index, buttonID in enumerate(self.buttonIDs)]
			else:
				currentButtonName = currentButton.getLabel()
				newButtonName = newButton.getLabel()
				currentButton.setLabel(newButtonName)
				newButton.setLabel(currentButtonName)

		self.setFocus(newButton)

	def getLabel(self, buttonID):
		return self.getButton(buttonID).getLabel()

	def getButton(self, buttonID):
		return self.getControl(buttonID)

	def createButtons(self):
		buttons = []
		spacing = 60
		buttonWidth = 120
		buttonHeight = 30
		font = "font14"

		self.buttonOK = xbmcgui.ControlButton(
			self.x + buttonWidth + 20,
			self.y + spacing,
			80,
			buttonHeight,
			"OK",
			font=font,
			noFocusTexture=self.grayTexture,
			focusTexture=self.blueTexture,
		)
		self.buttonClose = xbmcgui.ControlButton(
			self.x + buttonWidth + 20,
			self.y + spacing + 35,
			80,
			buttonHeight,
			"Close",
			font=font,
			noFocusTexture=self.grayTexture,
			focusTexture=self.blueTexture,
		)

		for res in self.resolutions:
			buttons.append(
				xbmcgui.ControlButton(
					self.x + 10,
					self.y + spacing,
					buttonWidth,
					buttonHeight,
					res,
					noFocusTexture=self.grayTexture,
					focusTexture=self.blueTexture,
					font=font,
				)
			)
			spacing += 30

		self.addControls(buttons + [self.buttonOK, self.buttonClose])
		self.buttonIDs = [button.getId() for button in buttons]
		self.buttonCloseID = self.buttonClose.getId()

		self.buttonOKid = self.buttonOK.getId()
		self.menuButtons = [self.buttonOKid, self.buttonCloseID]
		self.setFocusId(self.buttonIDs[0])
