import os
import re
import sys
import glob
import json
import time
import urllib2

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

import constants
from . import account_manager, gdrive_api


class ContentEngine:

	def __init__(self):
		self.pluginHandle = int(sys.argv[1])
		self.settings = constants.settings
		self.accountManager = account_manager.AccountManager(self.settings)
		self.accounts = self.accountManager.accounts
		self.cloudService = gdrive_api.GoogleDrive()

	def run(self, dbID, dbType, filePath):
		mode = self.settings.getParameter("mode", "main").lower()
		pluginQueries = self.settings.parseQuery(sys.argv[2][1:])
		self.instance = pluginQueries.get("instance")
		self.dialog = xbmcgui.Dialog()

		modes = {
			"enroll_account": self.enrollAccount,
			"add_service_account": self.addServiceAccount,
			"set_default_account": self.setDefaultAccount,
			"add_fallback_account": self.addFallbackAccounts,
			"validate_accounts": self.validateAccounts,
			"delete_accounts": self.deleteAccounts,
			"settings_delete_account": self.settingsDeleteAccounts,
			"resolution_priority": self.resolutionPriority,
			"video": self.playVideo,
		}

		if mode == "main" and self.instance:
			self.createContextMenu()
		elif mode == "main" and not self.instance:
			self.createMenu()
		elif mode == "video":
			modes[mode](dbID, dbType, filePath)
		else:
			modes[mode]()

		xbmcplugin.endOfDirectory(self.pluginHandle)

	def addMenu(self, url, title):
		listitem = xbmcgui.ListItem(title)
		cm = [(self.settings.getLocalizedString(30211), "Addon.OpenSettings({})".format(self.settings.getAddonInfo("id")))]
		listitem.addContextMenuItems(cm, True)
		xbmcplugin.addDirectoryItem(self.pluginHandle, url, listitem)

	def createMenu(self):
		pluginURL = sys.argv[0]
		self.addMenu(pluginURL + "?mode=enroll_account", "[B]1. {}[/B]".format(self.settings.getLocalizedString(30207)))
		self.addMenu(pluginURL + "?mode=add_service_account", "[B]2. {}[/B]".format(self.settings.getLocalizedString(30214)))
		self.addMenu(pluginURL + "?mode=add_fallback_account", "[B]3. {}[/B]".format(self.settings.getLocalizedString(30220)))
		self.addMenu(pluginURL + "?mode=validate_accounts", "[B]4. {}[/B]".format(self.settings.getLocalizedString(30021)))
		self.addMenu(pluginURL + "?mode=delete_accounts", "[B]5. {}[/B]".format(self.settings.getLocalizedString(30022)))

		defaultAccountName, defaultAccountNumber = self.accountManager.getDefaultAccount()
		fallbackAccountNames, fallbackAccountNumbers = self.accountManager.getFallbackAccounts()

		for accountNumber, accountInfo in self.accounts.items():
			accountName = accountInfo["username"]
			instance = accountNumber

			if accountNumber == defaultAccountNumber:
				accountName = "[COLOR crimson][B]{}[/B][/COLOR]".format(accountName)
			elif accountNumber in fallbackAccountNumbers:
				accountName = "[COLOR deepskyblue][B]{}[/B][/COLOR]".format(accountName)

			self.addMenu("{}?mode=main&instance={}".format(pluginURL, instance), accountName)

		xbmcplugin.setContent(self.pluginHandle, "files")
		xbmcplugin.addSortMethod(self.pluginHandle, xbmcplugin.SORT_METHOD_LABEL)

	def createContextMenu(self):
		options = [
			self.settings.getLocalizedString(30219),
			self.settings.getLocalizedString(30002),
			self.settings.getLocalizedString(30023),
			self.settings.getLocalizedString(30159),
		]

		accountNumber = self.instance
		account = self.accounts[accountNumber]
		accountName = account["username"]
		fallbackAccounts = self.accountManager.getFallbackAccounts()
		fallbackAccountNames, fallbackAccountNumbers = fallbackAccounts

		if accountNumber in fallbackAccountNumbers:
			fallbackExists = True
			options.insert(0, self.settings.getLocalizedString(30212))
		else:
			fallbackExists = False
			options.insert(0, self.settings.getLocalizedString(30213))

		selection = self.dialog.contextmenu(options)

		if selection == 0:

			if fallbackExists:
				self.accountManager.removeFallbackAccount(accountName, accountNumber, fallbackAccounts)
			else:
				self.accountManager.addFallbackAccount(accountName, accountNumber, fallbackAccounts)

		elif selection == 1:
			self.accountManager.setDefaultAccount(accountName, accountNumber)

		elif selection == 2:
			newAccountName = self.dialog.input(self.settings.getLocalizedString(30002) + ": " + accountName)

			if not newAccountName:
				return

			account["username"] = newAccountName
			self.accountManager.renameAccount(accountName, accountNumber, newAccountName)

		elif selection == 3:
			self.cloudService.setAccount(account)
			validation = self.cloudService.refreshToken()

			if validation == "failed":
				selection = self.dialog.yesno(
					self.settings.getLocalizedString(30000),
					"{} {}".format(accountName, self.settings.getLocalizedString(30019)),
				)

				if not selection:
					return

				self.accountManager.deleteAccount(accountNumber)

				if accountNumber in fallbackAccountNumbers:
					self.accountManager.removeFallbackAccount(accountName, accountNumber, fallbackAccounts)

			else:
				self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30020))
				return

		elif selection == 4:
			selection = self.dialog.yesno(
				self.settings.getLocalizedString(30000),
				"{} {}?".format(
					self.settings.getLocalizedString(30121),
					accountName,
				)
			)

			if not selection:
				return

			self.accountManager.deleteAccount(accountNumber)

			if accountNumber in fallbackAccountNumbers:
				self.accountManager.removeFallbackAccount(accountName, accountNumber, fallbackAccounts)

		else:
			return

		xbmc.executebuiltin("Container.Refresh")

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

		self.accountManager.addAccount({"username": accountName, "email": email, "key": key})
		xbmc.executebuiltin("Container.Refresh")

	def setDefaultAccount(self):
		accountNames, accountNumbers = self.accountManager.getAccountNamesAndNumbers()
		selection = self.dialog.select(self.settings.getLocalizedString(30120), accountNames)

		if selection == -1:
			return

		self.accountManager.setDefaultAccount(accountNames[selection], accountNumbers[selection])

	def addFallbackAccounts(self):
		accountNames, accountNumbers = self.accountManager.getAccountNamesAndNumbers()
		fallbackAccountNames, fallbackAccountNumbers = self.accountManager.getFallbackAccounts()

		if fallbackAccountNumbers:
			fallbackAccountNumbers = [accountNumbers.index(n) for n in fallbackAccountNumbers if n in accountNumbers]
			selection = self.dialog.multiselect(
				self.settings.getLocalizedString(30120),
				accountNames,
				preselect=fallbackAccountNumbers,
			)
		else:
			selection = self.dialog.multiselect(self.settings.getLocalizedString(30120), accountNames)

		if selection is None:
			return

		self.accountManager.setFallbackAccounts([accountNames[i] for i in selection], [accountNumbers[i] for i in selection])
		xbmc.executebuiltin("Container.Refresh")

	def validateAccounts(self):
		fallbackAccountNames, fallbackAccountNumbers = self.accountManager.getFallbackAccounts()
		accountAmount = len(self.accounts)
		pDialog = xbmcgui.DialogProgress()

		pDialog.create(self.settings.getLocalizedString(30306))
		deletion = fallbackDeletion = False
		count = 1

		for accountNumber, accountInfo in list(self.accounts.items()):
			accountName = accountInfo["username"]

			if pDialog.iscanceled():
				return

			self.cloudService.setAccount(self.accounts[accountNumber])
			validation = self.cloudService.refreshToken()
			pDialog.update(int(round(float(count) / float(accountAmount) * 100)), accountName)
			count += 1

			if validation == "failed":
				selection = self.dialog.yesno(
					self.settings.getLocalizedString(30000),
					"{} {}".format(accountName, self.settings.getLocalizedString(30019)),
				)

				if not selection:
					continue

				self.accountManager.deleteAccount(accountNumber)
				deletion = True

				if accountNumber in fallbackAccountNumbers:
					fallbackDeletion = True
					fallbackAccountNames.remove(accountName)
					fallbackAccountNumbers.remove(accountNumber)

		pDialog.close()
		self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30020))

		if deletion:

			if fallbackDeletion:
				self.accountManager.setFallbackAccounts(fallbackAccountNames, fallbackAccountNumbers)

			xbmc.executebuiltin("Container.Refresh")

	def accountDeletion(func):

		def wrapper(self):
			accountNames, accountNumbers = self.accountManager.getAccountNamesAndNumbers()
			fallbackAccountNames, fallbackAccountNumbers = self.accountManager.getFallbackAccounts()
			selection = self.dialog.multiselect(self.settings.getLocalizedString(30158), accountNames)
			fallbackDeletion = False

			if not selection:
				return

			for accountIndex in selection:
				accountName = accountNames[accountIndex]
				accountNumber = accountNumbers[accountIndex]
				self.accountManager.deleteAccount(accountNumber)

				if accountNumber in fallbackAccountNumbers:
					fallbackDeletion = True
					fallbackAccountNames.remove(accountName)
					fallbackAccountNumbers.remove(accountNumber)

			if fallbackDeletion:
				self.accountManager.setFallbackAccounts(fallbackAccountNames, fallbackAccountNumbers)

			func(self)

		return wrapper

	@accountDeletion
	def deleteAccounts(self):
		self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30161))
		xbmc.executebuiltin("Container.Refresh")

	@accountDeletion
	def settingsDeleteAccounts(self):
		self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30160))

	def resolutionPriority(self):
		resolutions = self.settings.getSetting("resolution_priority").split(", ")
		resolutionOrder = ResolutionOrder(resolutions=resolutions)

		resolutionOrder.doModal()
		newOrder = resolutionOrder.priorityList
		del resolutionOrder

		if newOrder:
			self.settings.setSetting("resolution_priority", ", ".join(newOrder))

	def playVideo(self, dbID, dbType, filePath):

		def escape(path):
			magicCheck = re.compile("([*?[])")
			drive, tail = os.path.splitdrive(path)
			tail = magicCheck.sub(r"[\1]", tail)
			return drive + tail

		defaultAccount = self.settings.getSetting("default_account")

		if not defaultAccount:
			self.dialog.ok(self.settings.getLocalizedString(30000), self.settings.getLocalizedString(30005))
			return

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

				dbPath = xbmc.translatePath(self.settings.getSetting("video_db"))
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

			# resumeDBPath = xbmc.translatePath(self.settings.resumeDBPath)
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
		fileID = self.settings.getParameter("filename")
		driveURL = self.cloudService.constructDriveURL(fileID)

		self.cloudService.setAccount(self.accounts[defaultAccount])
		self.cloudService.refreshToken()
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
		data = "encrypted={}&account={}&url={}&transcoded={}&fileid={}".format(crypto, defaultAccount, driveURL, transcoded, fileID)
		req = urllib2.Request(url, data.encode("utf-8"))

		try:
			response = urllib2.urlopen(req)
			response.close()
		except urllib2.URLError as e:
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
			subtitles = glob.glob(escape(filePath.rstrip(".strm")) + "*[!gom]")
			item.setSubtitles(subtitles)
		else:
			subtitles = glob.glob(escape(os.path.dirname(filePath) + os.sep) + "*[!gom]")
			item.setSubtitles(subtitles)

		xbmcplugin.setResolvedUrl(self.pluginHandle, True, item)

		if dbID:
			widget = 0 if xbmc.getInfoLabel("Container.Content") else 1
			data = "dbid={}&dbtype={}&widget={}&track={}".format(dbID, dbType, widget, 1)
		else:
			data = "dbid={}&dbtype={}&widget={}&track={}".format(0, 0, 0, 0)

		url = "http://localhost:{}/start_player".format(serverPort)
		req = urllib2.Request(url, data.encode("utf-8"))
		response = urllib2.urlopen(req)
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
