import re
import os
import sys
import time
import urllib2
import xbmc
import xbmcgui
import xbmcplugin
import constants

PLUGIN_NAME = constants.PLUGIN_NAME
PLUGIN_HANDLE = int(sys.argv[1])
PLUGIN_URL = sys.argv[0]
CLOUD_SERVICE = constants.cloudservice2
SETTINGS = constants.addon


class AccountActions:

	@staticmethod
	def getDefaultAccount():
		return SETTINGS.getSetting("default_account_ui"), SETTINGS.getSetting("default_account")

	@staticmethod
	def setDefaultAccount(accountName, accountNumber):
		SETTINGS.setSetting("default_account_ui", accountName)
		SETTINGS.setSetting("default_account", accountNumber)

	@staticmethod
	def getAccounts(accountAmount):
		accountInstances, accountNames, accountNumbers = [], [], []

		for count in range(1, accountAmount + 1):
			instanceName = PLUGIN_NAME + str(count)
			username = SETTINGS.getSetting(instanceName + "_username")

			if username:
				accountInstances.append(instanceName)
				accountNames.append(username)
				accountNumbers.append(str(count))

		return accountInstances, accountNames, accountNumbers

	def renameAccount(self, instanceName, accountName, newAccountName):
		self.setAccountName(instanceName, newAccountName)
		defaultAccountName, defaultAccountNumber = self.getDefaultAccount()

		if defaultAccountName == accountName:
			self.setDefaultAccount(newAccountName, defaultAccountNumber)

		fallbackAccountNames, fallbackAccountNumbers = self.getFallbackAccounts()

		if accountName in fallbackAccountNames:
			fallbackAccountNames.remove(accountName)
			fallbackAccountNames.append(newAccountName)
			self.setFallbackAccounts(fallbackAccountNames, fallbackAccountNumbers)

	def deleteAccount(self, instanceName, accountName):
		SETTINGS.setSetting(instanceName + "_username", "")
		SETTINGS.setSetting(instanceName + "_code", "")
		SETTINGS.setSetting(instanceName + "_client_id", "")
		SETTINGS.setSetting(instanceName + "_client_secret", "")
		SETTINGS.setSetting(instanceName + "_auth_access_token", "")
		SETTINGS.setSetting(instanceName + "_auth_refresh_token", "")

		defaultAccountName, defaultAccountNumber = self.getDefaultAccount()

		if defaultAccountName == accountName:
			SETTINGS.setSetting("default_account_ui", "")
			SETTINGS.setSetting("default_account", "")

	@staticmethod
	def getAccountName(instanceName):
		return SETTINGS.getSetting(instanceName + "_username")

	@staticmethod
	def getAccountNumber(instanceName):
		return re.sub("[^\d]", "", instanceName)

	@staticmethod
	def setAccountName(instanceName, newAccountName):
		SETTINGS.setSetting(instanceName + "_username", newAccountName)

	@staticmethod
	def validateAccount(instanceName, userAgent):
		validation = CLOUD_SERVICE(PLUGIN_HANDLE, PLUGIN_URL, SETTINGS, instanceName, userAgent)
		validation.refreshToken()

		if not validation.failed:
			return True

	@staticmethod
	def getFallbackAccounts():
		fallbackAccountNames = SETTINGS.getSetting("fallback_accounts_ui")
		fallbackAccountNumbers = SETTINGS.getSetting("fallback_accounts")

		if fallbackAccountNames:
			return fallbackAccountNames.split(", "), fallbackAccountNumbers.split(",")
		else:
			return [], []

	@staticmethod
	def setFallbackAccounts(fallbackAccountNames, fallbackAccountNumbers):
		SETTINGS.setSetting("fallback_accounts_ui", ", ".join(fallbackAccountNames))
		SETTINGS.setSetting("fallback_accounts", ",".join(fallbackAccountNumbers))

		if fallbackAccountNames:
			SETTINGS.setSetting("fallback", "true")
		else:
			SETTINGS.setSetting("fallback", "false")

	def addFallbackAccount(self, accountName, accountNumber, fallbackAccounts):
		fallbackAccountNames, fallbackAccountNumbers = fallbackAccounts
		fallbackAccountNumbers.append(accountNumber)
		fallbackAccountNames.append(accountName)
		self.setFallbackAccounts(fallbackAccountNames, fallbackAccountNumbers)

	def removeFallbackAccount(self, accountName, accountNumber, fallbackAccounts):
		fallbackAccountNames, fallbackAccountNumbers = fallbackAccounts
		fallbackAccountNumbers.remove(accountNumber)
		fallbackAccountNames.remove(accountName)
		self.setFallbackAccounts(fallbackAccountNames, fallbackAccountNumbers)


class ContentEngine:

	def addMenu(self, url, title, totalItems=0, instanceName=None):
		listitem = xbmcgui.ListItem(title)

		if instanceName is not None:
			cm = [(SETTINGS.getLocalizedString(30211), "Addon.OpenSettings({})".format(SETTINGS.getAddonInfo("id")))]
			listitem.addContextMenuItems(cm, True)

		xbmcplugin.addDirectoryItem(PLUGIN_HANDLE, url, listitem, totalItems=totalItems)

	def run(self, dbID, dbType, filePath):
		mode = SETTINGS.getParameter("mode", "main").lower()
		userAgent = SETTINGS.getSetting("user_agent")
		accountAmount = SETTINGS.getSettingInt("account_amount")
		pluginQueries = SETTINGS.parseQuery(sys.argv[2][1:])
		accountActions = AccountActions()

		try:
			instanceName = (pluginQueries["instance"]).lower()
		except:
			instanceName = None

		if not instanceName and mode == "main":
			self.addMenu(PLUGIN_URL + "?mode=enroll", "[B]1. {}[/B]".format(SETTINGS.getLocalizedString(30207)), instanceName=True)
			self.addMenu(PLUGIN_URL + "?mode=fallback", "[B]2. {}[/B]".format(SETTINGS.getLocalizedString(30220)), instanceName=True)
			self.addMenu(PLUGIN_URL + "?mode=validate", "[B]3. {}[/B]".format(SETTINGS.getLocalizedString(30021)), instanceName=True)
			self.addMenu(PLUGIN_URL + "?mode=delete", "[B]4. {}[/B]".format(SETTINGS.getLocalizedString(30022)), instanceName=True)

			defaultAccountName, defaultAccountNumber = accountActions.getDefaultAccount()
			fallbackAccounts = accountActions.getFallbackAccounts()
			fallbackAccountNames, fallbackAccountNumbers = fallbackAccounts

			for count in range (1, accountAmount + 1):
				instanceName = PLUGIN_NAME + str(count)
				accountName = accountActions.getAccountName(instanceName)

				if accountName:
					count = str(count)

					if count == defaultAccountNumber:
						accountName = "[COLOR crimson][B]{}[/B][/COLOR]".format(accountName)
					elif count in fallbackAccountNumbers:
						accountName = "[COLOR deepskyblue][B]{}[/B][/COLOR]".format(accountName)

					self.addMenu("{}?mode=main&instance={}".format(
						PLUGIN_URL, instanceName),
						accountName,
						instanceName=instanceName,
					)

			xbmcplugin.setContent(PLUGIN_HANDLE, "files")
			xbmcplugin.addSortMethod(PLUGIN_HANDLE, xbmcplugin.SORT_METHOD_LABEL)

		elif instanceName and mode == "main":
			options = [
				SETTINGS.getLocalizedString(30219),
				SETTINGS.getLocalizedString(30002),
				SETTINGS.getLocalizedString(30023),
				SETTINGS.getLocalizedString(30159),
			]
			fallbackAccounts = accountActions.getFallbackAccounts()
			fallbackAccountNames, fallbackAccountNumbers = fallbackAccounts
			accountName = accountActions.getAccountName(instanceName)
			accountNumber = accountActions.getAccountNumber(instanceName)

			if accountNumber in fallbackAccountNumbers:
				fallbackExists = True
				options.insert(0, SETTINGS.getLocalizedString(30212))
			else:
				fallbackExists = False
				options.insert(0, SETTINGS.getLocalizedString(30213))

			selection = xbmcgui.Dialog().contextmenu(options)

			if selection == 0:

				if fallbackExists:
					accountActions.removeFallbackAccount(accountName, accountNumber, fallbackAccounts)
				else:
					accountActions.addFallbackAccount(accountName, accountNumber, fallbackAccounts)

			elif selection == 1:
				accountActions.setDefaultAccount(
					accountActions.getAccountName(instanceName),
					accountActions.getAccountNumber(instanceName),
				)

			elif selection == 2:
				newName = xbmcgui.Dialog().input(SETTINGS.getLocalizedString(30002) + ": " + accountName)

				if not newName:
					return

				accountActions.renameAccount(instanceName, accountName, newName)

			elif selection == 3:
				validated = accountActions.validateAccount(instanceName, userAgent)

				if not validated:
					selection = xbmcgui.Dialog().yesno(
						SETTINGS.getLocalizedString(30000),
						"{} {}".format(accountName, SETTINGS.getLocalizedString(30019)),
					)

					if not selection:
						return

					accountActions.deleteAccount(instanceName, accountName)

					if accountName in fallbackAccountNames:
						accountActions.removeFallbackAccount(accountName, accountNumber, fallbackAccounts)

				else:
					xbmcgui.Dialog().ok(SETTINGS.getLocalizedString(30000), SETTINGS.getLocalizedString(30020))
					return

			elif selection == 4:
				selection = xbmcgui.Dialog().yesno(
					SETTINGS.getLocalizedString(30000),
					"{} {}?".format(
						SETTINGS.getLocalizedString(30121),
						accountActions.getAccountName(instanceName),
					)
				)

				if not selection:
					return

				accountActions.deleteAccount(instanceName, accountName)

				if accountName in fallbackAccountNames:
					accountActions.removeFallbackAccount(accountName, accountNumber, fallbackAccounts)

			else:
				return

			xbmc.executebuiltin("Container.Refresh")

		elif mode == "enroll":
			import socket

			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.connect(("8.8.8.8", 80))
			address = s.getsockname()[0]
			s.close()

			selection = xbmcgui.Dialog().ok(
				SETTINGS.getLocalizedString(30000),
				"{} [B][COLOR blue]http://{}:{}/enroll[/COLOR][/B] {}".format(
					SETTINGS.getLocalizedString(30210),
					address,
					SETTINGS.getSetting("server_port"),
					SETTINGS.getLocalizedString(30218),
				)
			)

			if selection:
				xbmc.executebuiltin("Container.Refresh")

		elif mode == "make_default":
			accountActions.setDefaultAccount(
				accountActions.getAccountName(instanceName),
				accountActions.getAccountNumber(instanceName),
			)
			xbmc.executebuiltin("Container.Refresh")

		elif mode == "settings_default":
			accountInstances, accountNames, accountNumbers = accountActions.getAccounts(accountAmount)
			selection = xbmcgui.Dialog().select(SETTINGS.getLocalizedString(30120), accountNames)

			if selection == -1:
				return

			accountActions.setDefaultAccount(accountNames[selection], accountNumbers[selection])
			xbmc.executebuiltin("Container.Refresh")

		elif mode == "fallback":
			accountInstances, accountNames, accountNumbers = accountActions.getAccounts(accountAmount)
			fallbackAccountNames, fallbackAccountNumbers = accountActions.getFallbackAccounts()

			if fallbackAccountNumbers:
				fallbackAccountNumbers = [accountNumbers.index(n) for n in fallbackAccountNumbers if n in accountNumbers]
				selection = xbmcgui.Dialog().multiselect(
					SETTINGS.getLocalizedString(30120),
					accountNames,
					preselect=fallbackAccountNumbers,
				)
			else:
				selection = xbmcgui.Dialog().multiselect(SETTINGS.getLocalizedString(30120), accountNames)

			if selection is None:
				return

			accountActions.setFallbackAccounts([accountNames[i] for i in selection], [accountNumbers[i] for i in selection])
			xbmc.executebuiltin("Container.Refresh")

		elif mode == "validate":
			accountInstances, accountNames, accountNumbers = accountActions.getAccounts(accountAmount)
			fallbackAccounts = accountActions.getFallbackAccounts()
			fallbackAccountNames, fallbackAccountNumbers = accountActions.getFallbackAccounts()
			accounts = [n for n in range(accountAmount)]
			selection = xbmcgui.Dialog().multiselect(SETTINGS.getLocalizedString(30024), accountNames, preselect=accounts)

			if not selection:
				return

			for index_ in selection:
				instanceName = accountInstances[index_]
				accountName = accountNames[index_]
				accountNumber = accountNumbers[index_]
				validated = accountActions.validateAccount(instanceName, userAgent)

				if not validated:
					selection = xbmcgui.Dialog().yesno(
						SETTINGS.getLocalizedString(30000),
						"{} {}".format(accountName, SETTINGS.getLocalizedString(30019)),
					)

					if not selection:
						continue

					accountActions.deleteAccount(instanceName, accountName)

					if accountName in fallbackAccountNames:
						accountActions.removeFallbackAccount(accountName, accountNumber, fallbackAccounts)

			xbmcgui.Dialog().ok(SETTINGS.getLocalizedString(30000), SETTINGS.getLocalizedString(30020))
			xbmc.executebuiltin("Container.Refresh")

		elif mode in ("delete", "settings_delete"):
			accountInstances, accountNames, accountNumbers = accountActions.getAccounts(accountAmount)
			fallbackAccounts = accountActions.getFallbackAccounts()
			fallbackAccountNames, fallbackAccountNumbers = fallbackAccounts
			selection = xbmcgui.Dialog().multiselect(SETTINGS.getLocalizedString(30158), accountNames)

			if not selection:
				return

			for accountIndex in selection:
				accountInstance = accountInstances[accountIndex]
				accountName = accountNames[accountIndex]
				accountNumber = accountNumbers[accountIndex]
				accountActions.deleteAccount(accountInstance, accountName)

				if accountName in fallbackAccountNames:
					accountActions.removeFallbackAccount(accountName, accountNumber, fallbackAccounts)

			if mode == "settings_delete":
				xbmcgui.Dialog().ok(SETTINGS.getLocalizedString(30000), SETTINGS.getLocalizedString(30160))
			else:
				xbmcgui.Dialog().ok(SETTINGS.getLocalizedString(30000), SETTINGS.getLocalizedString(30161))
				xbmc.executebuiltin("Container.Refresh")

		elif mode == "video":
			instanceName = PLUGIN_NAME + str(SETTINGS.getSetting("default_account", 1))
			service = CLOUD_SERVICE(PLUGIN_HANDLE, PLUGIN_URL, SETTINGS, instanceName, userAgent)

			if service.failed:
				xbmcgui.Dialog().ok(SETTINGS.getLocalizedString(30000), SETTINGS.getLocalizedString(30005))
				return

			if not SETTINGS.getSetting("crypto_password") or not SETTINGS.getSetting("crypto_salt"):
				xbmcgui.Dialog().ok(SETTINGS.getLocalizedString(30000), SETTINGS.getLocalizedString(30208))
				return

			try:
				service
			except NameError:
				xbmcgui.Dialog().ok(
					SETTINGS.getLocalizedString(30000),
					SETTINGS.getLocalizedString(30051) + " " + SETTINGS.getLocalizedString(30052),
				)
				xbmc.log(SETTINGS.getLocalizedString(30051) + PLUGIN_NAME + "-login", xbmc.LOGERROR)
				return

			if (not dbID or not dbType) and not filePath:
				timeEnd = time.time() + 1

				while time.time() < timeEnd and (not dbID or not dbType):
					xbmc.executebuiltin("Dialog.Close(busydialog)")
					dbID = xbmc.getInfoLabel("ListItem.DBID")
					dbType = xbmc.getInfoLabel("ListItem.DBTYPE")

			resumePosition = 0
			resumeOption = False
			playbackAction = SETTINGS.getSetting("playback_action")

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

					import json

					jsonResponse = json.loads(jsonQuery.encode("utf-8"))

					try:
						resumeData = jsonResponse["result"][jsonKey]["resume"]
					except:
						return

					resumePosition = resumeData["position"]
					videoLength = resumeData["total"]

				elif filePath:
					from sqlite3 import dbapi2 as sqlite

					dbPath = xbmc.translatePath(SETTINGS.getSetting("video_db"))
					db = sqlite.connect(dbPath)
					dirPath = os.path.dirname(filePath) + os.sep
					fileName = os.path.basename(filePath)

					try:
						resumePosition = list(
							db.execute(
								"SELECT timeInSeconds FROM bookmark WHERE idFile=(SELECT idFile FROM files WHERE idPath=(SELECT idPath FROM path WHERE strPath=?) AND strFilename=?)",
								(dirPath, fileName)
							)
						)
					except:
						xbmcgui.Dialog().ok(
							SETTINGS.getLocalizedString(30000),
							SETTINGS.getLocalizedString(30221),
						)
						return

					if resumePosition:
						resumePosition = resumePosition[0][0]
						videoLength = list(
							db.execute(
								"SELECT totalTimeInSeconds FROM bookmark WHERE idFile=(SELECT idFile FROM files WHERE idPath=(SELECT idPath FROM path WHERE strPath=?) AND strFilename=?)",
								(dirPath, fileName)
							)
						)[0][0]
					else:
						resumePosition = 0

				# import pickle

				# resumeDBPath = xbmc.translatePath(SETTINGS.resumeDBPath)
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

				# strmName = SETTINGS.getParameter("title") + ".strm"
				# cursor = list(db.execute("SELECT timeInSeconds FROM bookmark WHERE idFile=(SELECT idFile FROM files WHERE strFilename='%s')" % strmName))

				# if cursor:
					# resumePosition = cursor[0][0]
				# else:
					# resumePosition = 0

			if resumePosition > 0:

				if playbackAction == "Show resume prompt":
					options = ("Resume from " + str(time.strftime("%H:%M:%S", time.gmtime(resumePosition))), "Play from beginning")
					selection = xbmcgui.Dialog().contextmenu(options)

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

			# file ID
			driveID = SETTINGS.getParameter("filename")
			driveURL = "https://www.googleapis.com/drive/v2/files/{}?includeTeamDriveItems=true&supportsTeamDrives=true&alt=media".format(driveID)
			serverPort = SETTINGS.getSettingInt("server_port", 8011)
			url = "http://localhost:{}/crypto_playurl".format(serverPort)
			data = "instance={}&url={}".format(service.instanceName, driveURL)
			req = urllib2.Request(url, data.encode("utf-8"))

			try:
				response = urllib2.urlopen(req)
				response.close()
			except urllib2.URLError as e:
				xbmc.log(SETTINGS.getAddonInfo("name") + ": " + str(e), xbmc.LOGERROR)
				return

			item = xbmcgui.ListItem(path="http://localhost:{}/play".format(serverPort))
			# item.setProperty("StartPercent", str(position))
			# item.setProperty("startoffset", "60")

			if resumeOption:
				# item.setProperty("totaltime", "1")
				item.setProperty("totaltime", str(videoLength))
				item.setProperty("resumetime", str(resumePosition))

			xbmcplugin.setResolvedUrl(PLUGIN_HANDLE, True, item)

			if dbID:
				widget = 0 if xbmc.getInfoLabel("Container.Content") else 1
				data = "dbid={}&dbtype={}&widget={}&track={}".format(dbID, dbType, widget, 1)
			else:
				data = "dbid={}&dbtype={}&widget={}&track={}".format(0, 0, 0, 0)

			url = "http://localhost:{}/start_gplayer".format(serverPort)
			req = urllib2.Request(url, data.encode("utf-8"))
			response = urllib2.urlopen(req)
			response.close()

		xbmcplugin.endOfDirectory(PLUGIN_HANDLE)

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
