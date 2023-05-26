import os
import time
import urllib

import xbmc
import xbmcgui
import xbmcaddon

import constants
from .. import sync
from .. import filesystem


class SyncSettings(xbmcgui.WindowDialog):
	ACTION_MOVE_LEFT = 1
	ACTION_MOVE_RIGHT = 2
	ACTION_MOVE_UP = 3
	ACTION_MOVE_DOWN = 4
	ACTION_SELECT_ITEM = 7
	ACTION_BACKSPACE = 92
	LABELS_TO_SETTINGS = {
		constants.settings.getLocalizedString(30048): {"type": "global", "name": "local_path"},
		constants.settings.getLocalizedString(30049): {"type": "drive", "name": "task_mode"},
		constants.settings.getLocalizedString(30050): {"type": "drive", "name": "task_frequency"},
		constants.settings.getLocalizedString(30051): {"type": "drive", "name": "startup_sync"},
		constants.settings.getLocalizedString(30804): {"type": "folder", "name": "contains_encrypted"},
		constants.settings.getLocalizedString(30805): {"type": "folder", "name": "file_renaming"},
		constants.settings.getLocalizedString(30806): {"type": "folder", "name": "folder_restructure"},
		constants.settings.getLocalizedString(30807): {"type": "folder", "name": "sync_nfo"},
		constants.settings.getLocalizedString(30808): {"type": "folder", "name": "sync_subtitles"},
		constants.settings.getLocalizedString(30809): {"type": "folder", "name": "sync_artwork"},
		constants.settings.getLocalizedString(30058): {"type": "folder", "name": "tmdb_language"},
		constants.settings.getLocalizedString(30059): {"type": "folder", "name": "tmdb_region"},
		constants.settings.getLocalizedString(30060): {"type": "folder", "name": "tmdb_adult"},
	}
	def __init__(self, *args, **kwargs):
		self.displayMode = kwargs.get("mode")
		self.driveID = kwargs.get("drive_id")
		self.folderID = kwargs.get("folder_id")
		self.folderName = kwargs.get("folder_name")
		self.accounts = kwargs.get("accounts")
		self.cache = sync.cache.Cache()

		self.folders = False
		self.syncMode = None
		self.syncFrequency = None

		addon = xbmcaddon.Addon()
		self.dialog = xbmcgui.Dialog()

		texturesPath = os.path.join(addon.getAddonInfo("path"), "resources", "media")
		self.gDriveIconPath = os.path.join(texturesPath, "icon.png")
		self.radioButtonFocus = os.path.join(texturesPath, "radiobutton-focus.png")
		self.radioButtonNoFocus = os.path.join(texturesPath, "radiobutton-nofocus.png")
		self.buttonFocusTexture = os.path.join(texturesPath, "focus.png")
		self.blackTexture = os.path.join(texturesPath, "black.png")
		self.blueTexture = os.path.join(texturesPath, "blue.png")
		self.grayTexture = os.path.join(texturesPath, "gray.png")
		self.dGrayTexture = os.path.join(texturesPath, "dgray.png")
		self.createButtons()

	def setup(self, buttonAmount):
		self.font = "font13"
		self.viewportWidth = self.getWidth()
		self.viewportHeight = self.getHeight()
		self.windowWidth = int(1000 * self.viewportWidth / 1920)

		if self.folders:
			self.buttonWidth = self.windowWidth - 200
		else:
			self.buttonWidth = self.windowWidth - 50

		self.buttonHeight = 40
		self.windowHeight = int((400 + self.buttonHeight * buttonAmount) * self.viewportHeight / 1080)
		self.windowBottom = int((self.viewportHeight + self.windowHeight) / 2)

		self.x = int((self.viewportWidth - self.windowWidth) / 2)
		self.y = int((self.viewportHeight - self.windowHeight) / 2)
		self.center = int((self.x + self.windowWidth / 2) - (self.buttonWidth / 2))

		background = xbmcgui.ControlImage(self.x, self.y, self.windowWidth, self.windowHeight, self.grayTexture)
		bar = xbmcgui.ControlImage(self.x, self.y, self.windowWidth, 40, self.blueTexture)
		label = xbmcgui.ControlLabel(self.x + 10, self.y + 5, 0, 0, constants.settings.getLocalizedString(30012))
		self.addControls([background, bar, label])

	def onAction(self, action):
		action = action.getId()
		self.buttonID = self.getFocusId()

		if action == self.ACTION_BACKSPACE:
			self.close()
		elif action == self.ACTION_MOVE_UP:

			if self.buttonID == self.menuButtonIDs[0]:
				self.setFocus(self.buttonOK)
			elif self.buttonID in (self.buttonCloseID, self.buttonOKID):
				self.setFocusId(self.menuButtonIDs[-1])
			elif self.buttonID in self.menuButtonIDs:
				self.updateList("up")

		elif action == self.ACTION_MOVE_DOWN:

			if self.buttonID == self.menuButtonIDs[-1]:
				self.setFocus(self.buttonOK)
			elif self.buttonID in (self.buttonCloseID, self.buttonOKID):
				self.setFocusId(self.menuButtonIDs[0])
			elif self.buttonID in self.menuButtonIDs:
				self.updateList("down")

		elif action == self.ACTION_MOVE_RIGHT:

			if self.folders:

				if self.buttonID in self.menuButtonIDs or self.buttonID == self.buttonOKID:
					self.setFocus(self.buttonClose)
				elif self.buttonID in self.buttonSwitchesIDs:
					self.setFocusId(self.menuButtonIDs[0])
				elif self.buttonID == self.buttonCloseID:
					self.setFocusId(self.menuButtonIDs[0])

			else:

				if self.buttonID in self.menuButtonIDs or self.buttonID == self.buttonOKID:
					self.setFocus(self.buttonClose)
				elif self.buttonID == self.buttonCloseID:
					self.setFocusId(self.menuButtonIDs[0])

		elif action == self.ACTION_MOVE_LEFT:

			if self.folders:

				if self.buttonID in self.menuButtonIDs:
					self.setFocusId(self.buttonSwitchesIDs[0])
				elif self.buttonID in self.buttonSwitchesIDs:
					self.setFocus(self.buttonOK)
				elif self.buttonID == self.buttonCloseID:
					self.setFocus(self.buttonOK)
				elif self.buttonID == self.buttonOKID:
					self.setFocusId(self.menuButtonIDs[0])

			else:

				if self.buttonID in self.menuButtonIDs or self.buttonID == self.buttonCloseID:
					self.setFocus(self.buttonOK)
				elif self.buttonID == self.buttonOKID:
					self.setFocusId(self.menuButtonIDs[0])

	def onControl(self, control):
		self.buttonID = control.getId()

		if self.buttonID == self.buttonCloseID:
			self.close()
		elif self.buttonID == self.buttonOKID:
			self.setSettings()
		elif self.buttonID in self.pushButtonIDs:
			self.functions[control.getLabel()](control)
		elif self.buttonID in self.buttonSwitchesIDs:

			if self.buttonID == self.buttonSwitchesIDs[0]:
				[button.setVisible(False) for button in self.TMDBButtons]
				[button.setVisible(True) for button in self.generalSettingsButtons]
				self.menuButtonIDs = self.generalSettingsButtonIDs
			else:
				[button.setVisible(False) for button in self.generalSettingsButtons]
				[button.setVisible(True) for button in self.TMDBButtons]
				self.menuButtonIDs = self.TMDBButtonIDs

	def updateList(self, direction):
		currentIndex = self.menuButtonIDs.index(self.buttonID)

		if direction == "up":
			newIndex = currentIndex - 1
		elif direction == "down":
			newIndex = currentIndex + 1

			if newIndex == len(self.menuButtonIDs):
				newIndex = 0

		newButton = self.getButton(self.menuButtonIDs[newIndex])
		self.setFocus(newButton)

	def getLabel(self, buttonID):
		return self.getButton(buttonID).getLabel()

	def getButton(self, buttonID):
		return self.getControl(buttonID)

	def createDriveSettingsButtons(self):
		driveSettings = self.cache.getDrive(self.driveID)
		self.functions = {
			constants.settings.getLocalizedString(30049): self.setSyncMode,
			constants.settings.getLocalizedString(30050): self.setSyncFrequency,
			constants.settings.getLocalizedString(30061): self.stopAllFoldersSync,
			constants.settings.getLocalizedString(30062): self.stopAllFoldersSyncAndDelete,
		}
		self.syncMode = driveSettings["task_mode"]
		self.syncFrequency = driveSettings["task_frequency"]
		settings = {constants.settings.getLocalizedString(30051): driveSettings["startup_sync"]}
		self.setup(len(self.functions) + len(settings))

		for setting, value in settings.items():
			button = xbmcgui.ControlRadioButton(
				x=self.center,
				y=self.y + self.buttonSpacing,
				width=self.buttonWidth,
				height=self.buttonHeight,
				label=setting,
				font=self.font,
				noFocusOffTexture=self.radioButtonNoFocus,
				focusOffTexture=self.radioButtonNoFocus,
				focusOnTexture=self.radioButtonFocus,
				noFocusOnTexture=self.radioButtonFocus,
				focusTexture=self.buttonFocusTexture,
				noFocusTexture=self.dGrayTexture,
			)
			self.radioButtons[button] = setting
			self.addControl(button)
			button.setSelected(value)
			self.buttonSpacing += 40

		for func in self.functions:
			button = xbmcgui.ControlButton(
				x=self.center,
				y=self.y + self.buttonSpacing,
				width=self.buttonWidth,
				height=self.buttonHeight,
				label=func,
				font=self.font,
				focusTexture=self.buttonFocusTexture,
				noFocusTexture=self.dGrayTexture,
			)

			if func == constants.settings.getLocalizedString(30049):
				button.setLabel(label2=self.syncMode)
			elif func == constants.settings.getLocalizedString(30050):
				button.setLabel(label2=self.syncFrequency)

			self.pushButtons[button] = func
			self.addControl(button)
			self.buttonSpacing += 40

		self.generalSettingsButtons = list(self.radioButtons.keys()) + list(self.pushButtons.keys())
		self.generalSettingsButtonIDs = [button.getId() for button in self.generalSettingsButtons]
		self.menuButtonIDs = self.generalSettingsButtonIDs

	def createFolderSettingsButtons(self):
		settings = {}
		folderSettings = self.cache.getFolder(self.folderID)

		if not self.displayMode == "new" and folderSettings:
			self.functions = {
				constants.settings.getLocalizedString(30063): self.stopFolderSync,
				constants.settings.getLocalizedString(30064): self.stopFolderSyncAndDelete,
			}
		else:

			if not self.cache.getSyncRootPath():
				self.functions.update({constants.settings.getLocalizedString(30048): self.setSyncPath})

			if not self.cache.getDrive(self.driveID):
				settings.update({constants.settings.getLocalizedString(30051): False})
				self.functions.update(
					{
						constants.settings.getLocalizedString(30049): self.setSyncMode,
						constants.settings.getLocalizedString(30050): self.setSyncFrequency,
					}
				)

		settings.update(
			{
				constants.settings.getLocalizedString(30804): folderSettings["contains_encrypted"] if folderSettings else constants.settings.getSetting("contains_encrypted"),
				constants.settings.getLocalizedString(30805): folderSettings["file_renaming"] if  folderSettings else constants.settings.getSetting("file_renaming"),
				constants.settings.getLocalizedString(30806): folderSettings["folder_restructure"] if folderSettings else constants.settings.getSetting("folder_restructure"),
				constants.settings.getLocalizedString(30807): folderSettings["sync_nfo"] if folderSettings else constants.settings.getSetting("sync_nfo"),
				constants.settings.getLocalizedString(30808): folderSettings["sync_subtitles"] if folderSettings else constants.settings.getSetting("sync_subtitles"),
				constants.settings.getLocalizedString(30809): folderSettings["sync_artwork"] if folderSettings else constants.settings.getSetting("sync_artwork"),
			}
		)
		self.setup(len(self.functions) + len(settings))

		for setting in self.functions:
			button = xbmcgui.ControlButton(
				x=self.center + 80,
				y=self.y + self.buttonSpacing,
				width=self.buttonWidth,
				height=self.buttonHeight,
				label=setting,
				font=self.font,
				focusTexture=self.buttonFocusTexture,
				noFocusTexture=self.dGrayTexture,
			)
			self.pushButtons[button] = setting
			self.addControl(button)
			self.buttonSpacing += 40

		for setting, value in settings.items():
			button = xbmcgui.ControlRadioButton(
				x=self.center + 80,
				y=self.y + self.buttonSpacing,
				width=self.buttonWidth,
				height=self.buttonHeight,
				label=setting,
				font=self.font,
				noFocusOffTexture=self.radioButtonNoFocus,
				focusOffTexture=self.radioButtonNoFocus,
				focusOnTexture=self.radioButtonFocus,
				noFocusOnTexture=self.radioButtonFocus,
				focusTexture=self.buttonFocusTexture,
				noFocusTexture=self.dGrayTexture,
			)
			self.radioButtons[button] = setting
			self.addControl(button)
			button.setSelected(value)
			self.buttonSpacing += 40

		self.generalSettingsButtons = list(self.pushButtons.keys()) + list(self.radioButtons.keys())
		self.generalSettingsButtonIDs = [button.getId() for button in self.generalSettingsButtons]
		self.menuButtonIDs = self.generalSettingsButtonIDs

	def createFolderSettingsTMDBButtons(self):
		functions = {
			constants.settings.getLocalizedString(30058): self.setSearchLanguage,
			constants.settings.getLocalizedString(30059): self.setCountry,
			constants.settings.getLocalizedString(30060): self.setAdultContent,
		}
		self.functions.update(functions)
		self.buttonSwitchesIDs = []
		buttonGeneral = xbmcgui.ControlButton(
			x=self.center - 80,
			y=self.y + 60,
			width=140,
			height=self.buttonHeight,
			label=constants.settings.getLocalizedString(30065),
			font=self.font,
			focusTexture=self.buttonFocusTexture,
			noFocusTexture=self.dGrayTexture,
			alignment=2 + 4,
		)
		self.addControl(buttonGeneral)
		self.buttonSwitchesIDs.append(buttonGeneral.getId())

		buttonTMDB = xbmcgui.ControlButton(
			x=self.center - 80,
			y=self.y + 100,
			width=140,
			height=self.buttonHeight,
			label="TMDB",
			font=self.font,
			focusTexture=self.buttonFocusTexture,
			noFocusTexture=self.dGrayTexture,
			alignment=2 + 4,
		)
		self.addControl(buttonTMDB)
		self.buttonSwitchesIDs.append(buttonTMDB.getId())
		buttonGeneral.controlUp(buttonTMDB)
		buttonGeneral.controlDown(buttonTMDB)
		buttonTMDB.controlUp(buttonGeneral)
		buttonTMDB.controlDown(buttonGeneral)
		buttonSpacing = 60

		self.TMDBButtonIDs = []
		self.TMDBButtons = []
		folderSettings = self.cache.getFolder(self.folderID)

		if folderSettings:
			values = [
				folderSettings["tmdb_language"],
				folderSettings["tmdb_region"],
				folderSettings["tmdb_adult"],
			]
		else:
			values = [
				constants.settings.getSetting("tmdb_language") if constants.settings.getSetting("tmdb_language") else "",
				constants.settings.getSetting("tmdb_region") if constants.settings.getSetting("tmdb_region") else "",
				"true" if constants.settings.getSetting("tmdb_adult") else "false",
			]

		for func, value in zip(functions, values):
			button = xbmcgui.ControlButton(
				x=self.center + 80,
				y=self.y + buttonSpacing,
				width=self.buttonWidth,
				height=self.buttonHeight,
				label=func,
				font=self.font,
				focusTexture=self.buttonFocusTexture,
				noFocusTexture=self.dGrayTexture,
			)
			button.setVisible(False)
			button.setLabel(label2=value)
			self.pushButtons[button] = func
			self.addControl(button)
			buttonSpacing += 40
			self.TMDBButtonIDs.append(button.getId())
			self.TMDBButtons.append(button)

	def createButtons(self):
		self.buttonSpacing = 60
		self.radioButtons, self.pushButtons, self.functions = {}, {}, {}

		if self.displayMode in ("new", "folder"):
			self.folders = True
			self.createFolderSettingsButtons()
			self.createFolderSettingsTMDBButtons()
		else:
			self.createDriveSettingsButtons()

		self.pushButtonIDs = [button.getId() for button in self.pushButtons]
		self.radioButtonIDs = [button.getId() for button in self.radioButtons]

		self.buttonOK = xbmcgui.ControlButton(
			x=self.center + 80 if self.folders else self.center,
			y=self.windowBottom - 60,
			width=100,
			height=self.buttonHeight,
			label=constants.settings.getLocalizedString(30066),
			font=self.font,
			noFocusTexture=self.dGrayTexture,
			focusTexture=self.buttonFocusTexture,
			alignment=2 + 4,
		)
		self.buttonClose = xbmcgui.ControlButton(
			x=self.center + 200 if self.folders else self.center + 120,
			y=self.windowBottom - 60,
			width=100,
			height=self.buttonHeight,
			label=constants.settings.getLocalizedString(30067),
			font=self.font,
			noFocusTexture=self.dGrayTexture,
			focusTexture=self.buttonFocusTexture,
			alignment=2 + 4,
		)
		self.addControls([self.buttonOK, self.buttonClose])
		self.buttonCloseID = self.buttonClose.getId()
		self.buttonOKID = self.buttonOK.getId()
		self.setFocusId(self.menuButtonIDs[0])

	def setSyncMode(self, button):
		modes = [constants.settings.getLocalizedString(30068), constants.settings.getLocalizedString(30069)]
		selection = self.dialog.select(constants.settings.getLocalizedString(30049), modes)

		if selection == -1:
			return

		selection =  modes[selection]

		if selection != self.syncMode:
			[button.setLabel(label2=" ") for button, setting in self.pushButtons.items() if setting == constants.settings.getLocalizedString(30050)]
			self.syncMode = selection
			button.setLabel(label2=self.syncMode)

	def setSyncFrequency(self, button):

		if not self.syncMode:
			return

		if self.syncMode == constants.settings.getLocalizedString(30068):
			syncFrequency = self.dialog.numeric(0, constants.settings.getLocalizedString(30070))
		else:
			syncFrequency = self.dialog.numeric(2, constants.settings.getLocalizedString(30071))

		if syncFrequency:
			button.setLabel(label2=syncFrequency)

	def stopFolderSync(self, *args):
		selection = self.dialog.yesno(constants.settings.getLocalizedString(30000), constants.settings.getLocalizedString(30072))

		if not selection:
			return

		self.close()
		xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
		data = f"folder_id={self.folderID}&delete=False"
		url = f"http://localhost:{constants.settings.getSettingInt('server_port', 8011)}/stop_folder_sync"
		req = urllib.request.Request(url, data.encode("utf-8"))
		response = urllib.request.urlopen(req)
		response.close()
		xbmc.executebuiltin("Container.Refresh")
		xbmc.executebuiltin("Dialog.Close(busydialognocancel)")

	def stopAllFoldersSync(self, *args):
		selection = self.dialog.yesno(constants.settings.getLocalizedString(30000), constants.settings.getLocalizedString(30073))

		if not selection:
			return

		self.close()
		xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
		data = f"drive_id={self.driveID}&delete=False"
		url = f"http://localhost:{constants.settings.getSettingInt('server_port', 8011)}/stop_all_folders_sync"
		req = urllib.request.Request(url, data.encode("utf-8"))
		response = urllib.request.urlopen(req)
		response.close()
		xbmc.executebuiltin("Container.Refresh")
		xbmc.executebuiltin("Dialog.Close(busydialognocancel)")

	def stopFolderSyncAndDelete(self, *args):
		selection = self.dialog.yesno(constants.settings.getLocalizedString(30000), constants.settings.getLocalizedString(30074))

		if not selection:
			return

		self.close()
		xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
		self.dialog.notification(constants.settings.getLocalizedString(30000), constants.settings.getLocalizedString(30075), self.gDriveIconPath)
		data = f"folder_id={self.folderID}&delete=True"
		url = f"http://localhost:{constants.settings.getSettingInt('server_port', 8011)}/stop_folder_sync"
		req = urllib.request.Request(url, data.encode("utf-8"))
		response = urllib.request.urlopen(req)
		response.close()
		xbmc.executebuiltin("Container.Refresh")
		xbmc.executebuiltin("Dialog.Close(busydialognocancel)")

	def stopAllFoldersSyncAndDelete(self, *args):
		selection = self.dialog.yesno(constants.settings.getLocalizedString(30000), constants.settings.getLocalizedString(30076))

		if not selection:
			return

		self.close()
		xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
		self.dialog.notification(constants.settings.getLocalizedString(30000), constants.settings.getLocalizedString(30075), self.gDriveIconPath)
		data = f"drive_id={self.driveID}&delete=True"
		url = f"http://localhost:{constants.settings.getSettingInt('server_port', 8011)}/stop_all_folders_sync"
		req = urllib.request.Request(url, data.encode("utf-8"))
		response = urllib.request.urlopen(req)
		response.close()
		xbmc.executebuiltin("Container.Refresh")
		xbmc.executebuiltin("Dialog.Close(busydialognocancel)")

	def setSyncPath(self, button):
		syncRootPath = self.dialog.browse(0, constants.settings.getLocalizedString(30077), "files")

		if not syncRootPath:
			return

		syncRootPath = os.path.join(syncRootPath, constants.settings.getLocalizedString(30000))
		button.setLabel(label2=syncRootPath)

	def setSettings(self):
		globalSettings, driveSettings, folderSettings = {}, {}, {}
		settingTypes = {"global": globalSettings, "drive": driveSettings, "folder": folderSettings}

		for button, label in self.radioButtons.items():
			setting = self.LABELS_TO_SETTINGS[label]
			settingType = setting["type"]
			settingTypes[settingType].update({setting["name"]: button.isSelected()})

		for button, label in self.pushButtons.items():

			try:
				setting = self.LABELS_TO_SETTINGS[label]
				settingType = setting["type"]
				settingTypes[settingType].update({setting["name"]: button.getLabel2()})
			except KeyError:
				continue

		if folderSettings.get("contains_encrypted"):
			cryptoSalt = constants.settings.getSetting("crypto_salt")
			cryptoPassword = constants.settings.getSetting("crypto_password")

			if not cryptoSalt or not cryptoPassword:
				self.dialog.ok(constants.settings.getLocalizedString(30000), constants.settings.getLocalizedString(30078))
				return

		if globalSettings and not globalSettings["local_path"]:
			self.dialog.ok(constants.settings.getLocalizedString(30000), constants.settings.getLocalizedString(30079))
			return

		if self.displayMode == "drive" or not self.cache.getDrive(self.driveID):

			if not driveSettings["task_mode"]:
				self.dialog.ok(constants.settings.getLocalizedString(30000), constants.settings.getLocalizedString(30080))
				return

			if driveSettings["task_frequency"] == " ":
				self.dialog.ok(constants.settings.getLocalizedString(30000), constants.settings.getLocalizedString(30081))
				return

		self.close()

		if self.displayMode == "new":
			xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
			self.dialog.notification(constants.settings.getLocalizedString(30000), constants.settings.getLocalizedString(30082), self.gDriveIconPath)
			self.folderName = self.folderName_ = filesystem.helpers.removeProhibitedFSchars(self.folderName)
			remoteName = self.folderName
			copy = 1

			while self.cache.getFolder(self.folderName, column="local_path"):
				self.folderName = f"{self.folderName_} ({copy})"
				copy += 1

			if globalSettings:
				globalSettings.update({"operating_system": os.name})
				self.cache.addGlobalData(globalSettings)

			if driveSettings:
				alias = self.accounts[self.driveID]["alias"]
				drivePath = alias if alias else self.driveID

				driveSettings.update(
					{
						"drive_id": self.driveID,
						"local_path": drivePath,
						"last_update": time.time(),

					}
				)
				self.cache.addDrive(driveSettings)

			folderSettings.update(
				{
					"drive_id": self.driveID,
					"folder_id": self.folderID,
					"local_path": self.folderName,
					"remote_name": remoteName,
				}
			)
			self.cache.addFolder(folderSettings)
			data = f"drive_id={self.driveID}&folder_id={self.folderID}&folder_name={remoteName}"
			url = f"http://localhost:{constants.settings.getSettingInt('server_port', 8011)}/add_sync_task"
			req = urllib.request.Request(url, data.encode("utf-8"))
			response = urllib.request.urlopen(req)
			response.close()
			xbmc.executebuiltin("Container.Refresh")
			xbmc.executebuiltin("Dialog.Close(busydialognocancel)")

		else:

			if driveSettings:
				self.cache.updateDrive(driveSettings, self.driveID)
				data = f"drive_id={self.driveID}"
				url = f"http://localhost:{constants.settings.getSettingInt('server_port', 8011)}/renew_task"
				req = urllib.request.Request(url, data.encode("utf-8"))
				response = urllib.request.urlopen(req)
				response.close()

			if folderSettings:
				self.cache.updateFolder(folderSettings, self.folderID)

	def setSearchLanguage(self, button):
		selection = self.dialog.select(constants.settings.getLocalizedString(30810), filesystem.constants.TMDB_LANGUAGES)

		if selection == -1:
			return

		button.setLabel(label2=filesystem.constants.TMDB_LANGUAGES[selection])

	def setCountry(self, button):
		selection = self.dialog.select(constants.settings.getLocalizedString(30811), filesystem.constants.TMDB_REGIONS)

		if selection == -1:
			return

		button.setLabel(label2=filesystem.constants.TMDB_REGIONS[selection])

	def setAdultContent(self, button):
		options = ["true", "false"]
		selection = self.dialog.select(constants.settings.getLocalizedString(30812), options)

		if selection == -1:
			return

		button.setLabel(label2=options[selection])
