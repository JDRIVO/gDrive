import json


class AccountManager:

	def __init__(self, settings):
		self.settings = settings
		accounts = self.settings.getSetting("accounts")

		if accounts:
			self.accounts = json.loads(accounts)
		else:
			self.getAccounts()

	def getDefaultAccount(self):
		return self.settings.getSetting("default_account_ui"), self.settings.getSetting("default_account")

	def setDefaultAccount(self, accountName, accountNumber):
		self.settings.setSetting("default_account_ui", accountName)
		self.settings.setSetting("default_account", accountNumber)

	# Convert old settings format to new dictionary format
	def getAccounts(self):
		accounts = {}
		accountAmount = self.settings.getSettingInt("account_amount")

		for accountNumber in range(1, accountAmount + 1):
			accountNumber = str(accountNumber)
			instanceName = "gdrive" + accountNumber
			accountName = self.settings.getSetting(instanceName + "_username")
			code = self.settings.getSetting(instanceName + "_code")

			clientID = self.settings.getSetting(instanceName + "_client_id")
			clientSecret = self.settings.getSetting(instanceName + "_client_secret")
			refreshToken = self.settings.getSetting(instanceName + "_auth_refresh_token")

			if accountName:
				accounts[accountNumber] = {
					"username": accountName,
					"code": code,
					"client_id": clientID,
					"client_secret": clientSecret,
					"refresh_token": refreshToken,
				}

		self.accounts = accounts
		self.saveAccounts()
		return accounts

	def saveAccounts(self):
		self.settings.setSetting("accounts", json.dumps(self.accounts))

	def loadAccounts(self):
		self.accounts = json.loads(self.settings.getSetting("accounts"))

	def addAccount(self, accountInfo):
		accountNumber = 1

		while True:
			accountNumberString = str(accountNumber)

			if accountNumberString not in self.accounts:
				break
			else:
				accountNumber += 1

		self.accounts[accountNumberString] = accountInfo
		self.saveAccounts()
		return accountNumberString

	def renameAccount(self, accountName, accountNumber, newAccountName):
		self.saveAccounts()
		defaultAccountName, defaultAccountNumber = self.getDefaultAccount()

		if defaultAccountNumber == accountNumber:
			self.setDefaultAccount(newAccountName, defaultAccountNumber)

		fallbackAccountNames, fallbackAccountNumbers = self.getFallbackAccounts()

		if accountNumber in fallbackAccountNumbers:
			fallbackAccountNames.remove(accountName)
			fallbackAccountNames.append(newAccountName)
			self.setFallbackAccounts(fallbackAccountNames, fallbackAccountNumbers)

	def deleteAccount(self, accountNumber):
		del self.accounts[accountNumber]
		defaultAccountName, defaultAccountNumber = self.getDefaultAccount()
		self.saveAccounts()

		if defaultAccountNumber == accountNumber:
			self.settings.setSetting("default_account_ui", "")
			self.settings.setSetting("default_account", "")

	def getAccountNamesAndNumbers(self):
		accountNames, accountNumbers = [], []
		[(accountNames.append(accountInfo["username"]), accountNumbers.append(number)) for number, accountInfo in self.accounts.items()]
		return accountNames, accountNumbers

	def validateAccount(self, cloudService, account):
		cloudService.account = account
		validatorResult = cloudService.refreshToken()
		return validatorResult

	def getFallbackAccounts(self):
		fallbackAccountNames = self.settings.getSetting("fallback_accounts_ui")
		fallbackAccountNumbers = self.settings.getSetting("fallback_accounts")

		if fallbackAccountNames:
			return fallbackAccountNames.split(", "), fallbackAccountNumbers.split(",")
		else:
			return [], []

	def setFallbackAccounts(self, fallbackAccountNames, fallbackAccountNumbers):
		self.settings.setSetting("fallback_accounts_ui", ", ".join(fallbackAccountNames))
		self.settings.setSetting("fallback_accounts", ",".join(fallbackAccountNumbers))

		if fallbackAccountNames:
			self.settings.setSetting("fallback", "true")
		else:
			self.settings.setSetting("fallback", "false")

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
