import json


class AccountManager:

	def __init__(self, settings):
		self.settings = settings
		accounts = self.settings.getSetting("accounts")

		if accounts:
			self.accounts = json.loads(accounts)
		else:
			self.accounts = {}

	def getAccount(self, driveID):
		accounts = self.accounts[driveID]

		if accounts:
			return [account for account in self.accounts[driveID] if "service" not in account][0]

	def getAccounts(self, driveID):
		return self.accounts[driveID]

	def saveAccounts(self):
		self.settings.setSetting("accounts", json.dumps(self.accounts))

	def loadAccounts(self):

		try:
			self.accounts = json.loads(self.settings.getSetting("accounts"))
		except:
			self.accounts = {}

	def addAccount(self, accountInfo, driveID):
		accounts = self.accounts.get(driveID)

		if accounts:
			accounts.insert(0, accountInfo)
		else:
			self.accounts[driveID] = [accountInfo]

		self.saveAccounts()

	def renameAccount(self, driveID, accountIndex, newAccountName):
		self.accounts[driveID][accountIndex]["username"] = newAccountName
		self.saveAccounts()

	def deleteAccount(self, driveID, account):
		self.accounts[driveID].remove(account)
		self.saveAccounts()
