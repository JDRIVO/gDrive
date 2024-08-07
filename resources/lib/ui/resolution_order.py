import os

import xbmcgui
import xbmcaddon

import constants


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

		mediaPath = os.path.join(addon.getAddonInfo("path"), "resources", "media")
		self.blueTexture = os.path.join(mediaPath, "blue.png")
		self.grayTexture = os.path.join(mediaPath, "gray.png")
		self.dGrayTexture = os.path.join(mediaPath, "dgray.png")

		self.priorityList = None
		self.shift = False

		viewportWidth = self.getWidth()
		viewportHeight = self.getHeight()

		w = int(350 * viewportWidth / 1920)
		h = int(350 * viewportHeight / 1080)

		self.x = int((viewportWidth - w) / 2)
		self.y = int((viewportHeight - h) / 2)

		background = xbmcgui.ControlImage(self.x, self.y, w, h, self.grayTexture)
		bar = xbmcgui.ControlImage(self.x, self.y, w, 40, self.blueTexture)
		label = xbmcgui.ControlLabel(self.x + 10, self.y + 5, 0, 0, constants.settings.getLocalizedString(30083))

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
			constants.settings.getLocalizedString(30066),
			font=font,
			noFocusTexture=self.dGrayTexture,
			focusTexture=self.blueTexture,
			alignment=2 + 4,
		)
		self.buttonClose = xbmcgui.ControlButton(
			self.x + buttonWidth + 20,
			self.y + spacing + 35,
			80,
			buttonHeight,
			constants.settings.getLocalizedString(30084),
			font=font,
			noFocusTexture=self.dGrayTexture,
			focusTexture=self.blueTexture,
			alignment=2 + 4,
		)

		for res in self.resolutions:
			buttons.append(
				xbmcgui.ControlButton(
					self.x + 10,
					self.y + spacing,
					buttonWidth,
					buttonHeight,
					res,
					noFocusTexture=self.dGrayTexture,
					focusTexture=self.blueTexture,
					font=font,
					alignment=2 + 4,
				)
			)
			spacing += 30

		self.addControls(buttons + [self.buttonOK, self.buttonClose])
		self.buttonIDs = [button.getId() for button in buttons]
		self.buttonCloseID = self.buttonClose.getId()
		self.buttonOKid = self.buttonOK.getId()
		self.menuButtons = [self.buttonOKid, self.buttonCloseID]
		self.setFocusId(self.buttonIDs[0])
