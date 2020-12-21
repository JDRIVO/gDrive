'''
    CloudService XBMC Plugin
    Copyright (C) 2013-2014 ddurdle

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import re
import sys
import os
import urllib
import xbmc, xbmcgui, xbmcplugin, xbmcvfs

def decode(data):

	return re.sub("&#(\d+)(;|(?=\s))", _callback, data).strip()

def decode_dict(data):

	for k, v in data.items():

		if type(v) is str or type(v) is unicode:
			data[k] = decode(v)

	return data

#http://stackoverflow.com/questions/1208916/decoding-html-entities-with-python/1208931#1208931
def _callback(matches):
	id = matches.group(1)

	try:
		return unichr(int(id) )
	except:
		return id

class contentengine(object):
	plugin_handle = None
	PLUGIN_URL = ''

	##
	# load eclipse debugger
	#	parameters: none
	##
	def debugger(self):

		try:
			remote_debugger = settingsModule.getSetting('remote_debugger')
			remote_debugger_host = settingsModule.getSetting('remote_debugger_host')

			# append pydev remote debugger
			if remote_debugger == 'true':
				# Make pydev debugger works for auto reload.
				# Note pydevd module need to be copied in XBMC\system\python\Lib\pysrc
				import pysrc.pydevd as pydevd
				# stdoutToServer and stderrToServer redirect stdout and stderr to eclipse console
				pydevd.settrace(remote_debugger_host, stdoutToServer=True, stderrToServer=True)

		except ImportError:
			xbmc.log(self.addon.getLocalizedString(30016), xbmc.LOGERROR)
			sys.exit(1)
		except:
			return

	##
	# Delete an account, enroll an account or refresh the current listings
	#	parameters: mode
	##
	def accountActions(self, addon, mode, instanceName, accountAmount):

		if mode == 'makedefault':
			addon.setSetting('default_account', re.sub("[^\d]", '', instanceName) )
			addon.setSetting('default_account_ui', addon.getSetting(instanceName + '_username') )
			xbmc.executebuiltin("Container.Refresh")

		elif mode == 'rename':
			input = xbmcgui.Dialog().input(addon.getLocalizedString(30002) )

			if input == '':
				return

			accountName = addon.getSetting(instanceName + '_username')
			addon.setSetting(instanceName + '_username', input)

			if addon.getSetting('default_account_ui') == accountName:
				addon.setSetting('default_account_ui', input)

			fallbackAccounts = addon.getSetting('fallback_accounts_ui').split(', ')

			if accountName in fallbackAccounts:
				fallbackAccounts.remove(accountName)
				fallbackAccounts.append(input)
				addon.setSetting('fallback_accounts_ui', ', '.join(fallbackAccounts) )

			xbmc.executebuiltin("Container.Refresh")

		# delete the configuration for the specified account
		elif mode == 'delete':

			if instanceName != '':

				try:
					# gdrive specific ***
					accountName = addon.getSetting(instanceName + '_username')
					addon.setSetting(instanceName + '_username', '')
					addon.setSetting(instanceName + '_code', '')
					addon.setSetting(instanceName + '_client_id', '')
					addon.setSetting(instanceName + '_client_secret', '')
					addon.setSetting(instanceName + '_auth_access_token', '')
					addon.setSetting(instanceName + '_auth_refresh_token', '')

					if addon.getSetting('default_account_ui') == accountName:
						addon.setSetting('default_account_ui', '')
						addon.setSetting('default_account', '')

					fallbackAccountsUI = addon.getSetting('fallback_accounts_ui').split(', ')

					if accountName in fallbackAccountsUI:
						fallbackAccounts = addon.getSetting('fallback_accounts').split(',')
						fallbackAccounts.remove(re.sub("[^\d]", '', instanceName) )
						fallbackAccountsUI.remove(accountName)

						addon.setSetting('fallback_accounts', ','.join(fallbackAccounts) )
						addon.setSetting('fallback_accounts_ui', ', '.join(fallbackAccountsUI) )

					xbmcgui.Dialog().ok(addon.getLocalizedString(30000), addon.getLocalizedString(30158) )
					xbmc.executebuiltin("Container.Refresh")
				except:
					#error: instance doesn't exist
					xbmcgui.Dialog().ok(addon.getLocalizedString(30000), addon.getLocalizedString(30158) )

		# enroll a new account
		elif mode == 'enroll':

			import socket
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.connect( ("8.8.8.8", 80) )
			IP = s.getsockname()[0]
			s.close()

			display = xbmcgui.Dialog().ok(addon.getLocalizedString(30000), '%s [B][COLOR blue]http://%s:8011/enroll[/COLOR][/B] %s' % (addon.getLocalizedString(30210), IP, addon.getLocalizedString(30218) ) )

			if display:
				xbmc.executebuiltin("Container.Refresh")

		elif mode == 'deletefallback' or mode == 'addfallback':
			accountNumbers = addon.getSetting('fallback_accounts')
			accountNames = addon.getSetting('fallback_accounts_ui')
			accountName = addon.getSetting(instanceName + '_username')
			accountNumber = re.sub("[^\d]", '', instanceName)

			if accountNumbers != '':
				accountNumbers = accountNumbers.split(',')
				accountNames = accountNames.split(', ')

				if mode == 'deletefallback':
					accountNumbers.remove(accountNumber)
					accountNames.remove(accountName)
				else:
					accountNumbers.append(accountNumber)
					accountNames.append(accountName)

				addon.setSetting('fallback_accounts', ','.join(accountNumbers) )
				addon.setSetting('fallback_accounts_ui', ', '.join(accountNames) )
			else:
				addon.setSetting('fallback', 'true')
				addon.setSetting('fallback_accounts', accountNumber)
				addon.setSetting('fallback_accounts_ui', accountName)

			xbmc.executebuiltin("Container.Refresh")

	##
	# add a menu to a directory screen
	#	parameters: url to resolve, title to display, optional: icon, fanart, total_items, instance name
	##
	def addMenu(self, url, title, total_items=0, instanceName=None):
		listitem = xbmcgui.ListItem(title)

		if instanceName is not None:
			cm = []
			cm.append( (self.addon.getLocalizedString(30211), 'Addon.OpenSettings(%s)' % self.addon.getAddonInfo('id') ) )
			listitem.addContextMenuItems(cm, True)

		xbmcplugin.addDirectoryItem(self.plugin_handle, url, listitem, totalItems=total_items)

	##
	# Delete an account, enroll an account or refresh the current listings
	#	parameters: addon, plugin name, mode, instance name, user provided username, number of accounts, current context
	#	returns: selected instance name
	##
	def getInstanceName(self, addon, mode, instanceName, accountAmount, settingsModule):

		if accountAmount > 1 and instanceName == '' and mode == 'main':
			self.addMenu(self.PLUGIN_URL + '?mode=enroll', '[B]%s[/B]' % addon.getLocalizedString(30207) )
			self.addMenu(self.PLUGIN_URL + '?mode=fallback', '[B]%s[/B]' % addon.getLocalizedString(30220) )
			mode = ''

			defaultAccount = addon.getSetting("default_account_ui")
			fallBackAccounts = addon.getSetting("fallback_accounts_ui").split(', ')

			for count in range (1, accountAmount + 1):
				instanceName = self.PLUGIN_NAME + str(count)
				username = settingsModule.getSetting(instanceName + '_username', None)

				if username is not None and username != '':

					if username == defaultAccount:
						username = '[COLOR crimson][B]%s[/B][/COLOR]' % username
					elif username in fallBackAccounts:
						username = '[COLOR deepskyblue][B]%s[/B][/COLOR]' % username

					self.addMenu('%s?mode=main&instance=%s' % (self.PLUGIN_URL, instanceName), username, instanceName=instanceName)

			xbmcplugin.setContent(self.plugin_handle, "files")
			xbmcplugin.addSortMethod(self.plugin_handle, xbmcplugin.SORT_METHOD_LABEL)
			return None

		elif instanceName == '' and accountAmount == 1:
			options = []
			accounts = []

			for count in range (1, accountAmount + 1):
				instanceName = self.PLUGIN_NAME + str(count)

				try:
					username = settingsModule.getSetting(instanceName + '_username')

					if username != '' and username is not None:
						options.append(username)
						accounts.append(instanceName)

				except:
					return instanceName

			#fallback on first defined account
			return accounts[0]

		# no accounts defined
		elif accountAmount == 0:
			xbmcgui.Dialog().ok(addon.getLocalizedString(30000), addon.getLocalizedString(30015) )
			xbmcplugin.endOfDirectory(self.plugin_handle)
			return instanceName

		# show entries of a single account (such as folder)
		elif instanceName != '':
			return instanceName

	def run(self, dbID=None, dbType=None, filePath=None, writer=None, query=None, addon=None, host=None):
		from resources.lib import settings
		import constants

		addon = constants.addon
		self.addon = addon

		self.PLUGIN_URL = constants.PLUGIN_NAME
		self.PLUGIN_NAME = constants.PLUGIN_NAME
		cloudservice2 = constants.cloudservice2

		#global variables
		self.PLUGIN_URL = sys.argv[0]
		self.plugin_handle = int(sys.argv[1])
		plugin_queries = settings.parse_query(sys.argv[2][1:])

		# cloudservice - create settings module
		settingsModule = settings.settings(addon)

		user_agent = settingsModule.getSetting('user_agent')
		accountAmount = addon.getSettingInt('account_amount')
		mode = settingsModule.getParameter('mode', 'main')
		mode = mode.lower()

		try:
			instanceName = (plugin_queries['instance']).lower()
		except:
			instanceName = ''

		if instanceName and mode == 'main':
			fallbackAccounts = addon.getSetting('fallback_accounts').split(',')
			options = [self.addon.getLocalizedString(30219), self.addon.getLocalizedString(30002), self.addon.getLocalizedString(30159) ]
			account = re.sub("[^\d]", '', instanceName)
			fallback = False

			if account in fallbackAccounts:
				options.insert(0, self.addon.getLocalizedString(30212) )
				fallback = True
			else:
				options.insert(0, self.addon.getLocalizedString(30213) )

			selection = xbmcgui.Dialog().contextmenu(options)

			if selection == 0:

				if fallback:
					mode = "deletefallback"
				else:
					mode = "addfallback"

			elif selection == 1:
				mode = "makedefault"
			elif selection == 2:
				mode = "rename"
			elif selection == 3:
				mode = "delete"
			else:
				return

			self.accountActions(addon, mode, instanceName, accountAmount)
			return

		elif mode == 'enroll' or mode == 'makedefault' or mode == 'rename' or mode == 'delete':
			self.accountActions(addon, mode, instanceName, accountAmount)
			return

		elif mode == 'settings_default' or mode == 'settings_fallback' or mode == 'fallback':
			options = []
			accounts = []

			for count in range (1, accountAmount + 1):
				instanceName = self.PLUGIN_NAME + str(count)

				username = settingsModule.getSetting(instanceName + '_username')

				if username != '' and username is not None:
					options.append(username)
					accounts.append(instanceName)

			if mode == 'settings_default':
				ret = xbmcgui.Dialog().select(addon.getLocalizedString(30120), options)
			else:
				fallbackAccounts = addon.getSetting('fallback_accounts_ui')

				if fallbackAccounts != '':
					fallbackAccounts = [options.index(x) for x in fallbackAccounts.split(', ')]
					ret = xbmcgui.Dialog().multiselect(addon.getLocalizedString(30120), options, preselect=fallbackAccounts)
				else:
					ret = xbmcgui.Dialog().multiselect(addon.getLocalizedString(30120), options)

			if ret == -1 or not ret:
				return

			if mode == 'settings_default':
				addon.setSetting('default_account', re.sub("[^\d]", '', accounts[ret] ) )
				addon.setSetting('default_account_ui', options[ret])
			else:
				addon.setSetting('fallback_accounts', ','.join(re.sub("[^\d]", '', accounts[x] ) for x in ret ) )
				addon.setSetting('fallback_accounts_ui', ', '.join(options[x] for x in ret ) )

				if mode == 'fallback':
					addon.setSetting('fallback', 'true')
					xbmc.executebuiltin("Container.Refresh")

			return

		#STRM playback without instance name; use default
		if instanceName == '' and mode == 'video':
			instanceName = constants.PLUGIN_NAME + str(settingsModule.getSetting('default_account', 1) )

		instanceName = self.getInstanceName(addon, mode, instanceName, accountAmount, settingsModule)

		if mode == 'video':

			if not dbType and not dbID and not filePath:
				return

			if instanceName is None or instanceName == '':
				service = cloudservice2(self.plugin_handle, self.PLUGIN_URL, addon, '', user_agent, settingsModule, authenticate=False)
			else:
				service = cloudservice2(self.plugin_handle, self.PLUGIN_URL, addon, instanceName, user_agent, settingsModule)

			if service.failed:
				return

			if not settingsModule.cryptoPassword or not settingsModule.cryptoSalt:
				xbmcgui.Dialog().ok(addon.getLocalizedString(30000), addon.getLocalizedString(30208) )
				return

			driveID = settingsModule.getParameter('filename') #file ID

			try:
				service
			except NameError:
				xbmcgui.Dialog().ok(addon.getLocalizedString(30000), addon.getLocalizedString(30051) + " " + addon.getLocalizedString(30052) )
				xbmc.log(addon.getLocalizedString(30051) + constants.PLUGIN_NAME + '-login', xbmc.LOGERROR)
				xbmcplugin.endOfDirectory(self.plugin_handle)
				return

			resumeOption = False

			if dbID:

				if dbType == 'movie':
					jsonQuery = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": "1", "method": "VideoLibrary.GetMovieDetails", "params": { "movieid":' + str(dbID) + ', "properties": ["resume"] } }')
					jsonKey = 'moviedetails'
				else:
					jsonQuery = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": "1", "method": "VideoLibrary.GetEpisodeDetails", "params": { "episodeid":' + str(dbID) + ', "properties": ["resume"] } }')
					jsonKey = 'episodedetails'

				import json
				jsonQuery = jsonQuery.encode('utf-8', errors='ignore')
				jsonResponse = json.loads(jsonQuery)
				resumeData = jsonResponse['result'][jsonKey]['resume']

				resumePosition = resumeData['position']
				videoLength = resumeData['total']

			else:

				from sqlite3 import dbapi2 as sqlite
				dbPath = xbmc.translatePath(settingsModule.getSetting('video_db') )
				db = sqlite.connect(dbPath)

				dirPath = os.path.dirname(filePath) + os.sep
				fileName = os.path.basename(filePath)
				resumePosition = list(db.execute('SELECT timeInSeconds FROM bookmark WHERE idFile=(SELECT idFile FROM files WHERE idPath=(SELECT idPath FROM path WHERE strPath=?) AND strFilename=?)', (dirPath, fileName ) ) )

				if resumePosition:
					resumePosition = resumePosition[0][0]
					videoLength = list(db.execute('SELECT totalTimeInSeconds FROM bookmark WHERE idFile=(SELECT idFile FROM files WHERE idPath=(SELECT idPath FROM path WHERE strPath=?) AND strFilename=?)', (dirPath, fileName ) ) )[0][0]
				else:
					resumePosition = 0

				# import pickle

				# resumeDBPath = xbmcvfs.translatePath(settingsModule.resumeDBPath)
				# resumeDB = os.path.join(resumeDBPath, 'kodi_resumeDB.p')

				# try:
					# with open(resumeDB, 'rb') as dic:
						# videoData = pickle.load(dic)
				# except:
					# videoData = {}

				# try:
					# resumePosition = videoData[filename]
				# except:
					# videoData[filename] = 0
					# resumePosition = 0

				# strmName = settingsModule.getParameter('title') + ".strm"
				# cursor = list(db.execute('SELECT timeInSeconds FROM bookmark WHERE idFile=(SELECT idFile FROM files WHERE strFilename="%s")' % strmName) )

				# if cursor:
					# resumePosition = cursor[0][0]
				# else:
					# resumePosition = 0

			if resumePosition > 0:

				import time
				options = []
				options.append('Resume from ' + str(time.strftime("%H:%M:%S", time.gmtime(resumePosition) ) ) )
				options.append('Play from beginning')

				selection = xbmcgui.Dialog().contextmenu(options)

				if selection == 0:
					# resumePosition = resumePosition / total * 100
					resumeOption = True
				# elif selection == 1:
					# resumePosition = '0'
					# videoData[filename] = 0
				elif selection == -1:
					return

			driveURL = "https://www.googleapis.com/drive/v2/files/%s?includeTeamDriveItems=true&supportsTeamDrives=true&alt=media" % driveID
			url = 'http://localhost:' + str(service.settings.streamPort) + '/crypto_playurl'
			data = 'instance=' + str(service.instanceName) + '&url=' + driveURL
			req = urllib.request.Request(url, data.encode('utf-8') )

			try:
				response = urllib.request.urlopen(req)
				response.close()
			except urllib.error.URLError as e:
				xbmc.log(self.addon.getAddonInfo('name') + ': ' + str(e), xbmc.LOGERROR)
				return

			item = xbmcgui.ListItem(path='http://localhost:' + str(service.settings.streamPort) + '/play')
			# item.setProperty('StartPercent', str(position) )
			# item.setProperty('startoffset', '60')

			if resumeOption:
				# item.setProperty('totaltime', '1')
				item.setProperty('totaltime', str(videoLength) )
				item.setProperty('resumetime', str(resumePosition) )

			xbmcplugin.setResolvedUrl(self.plugin_handle, True, item)

			if dbID:

				from resources.lib import gplayer
				player = gplayer.gPlayer(dbID=dbID, dbType=dbType)

				# with open(resumeDB, 'wb+') as dic:
					# pickle.dump(videoData, dic)

				# del videoData

				xbmc.sleep(100)
				monitor = xbmc.Monitor()

				while not monitor.abortRequested() and not player.isExit:
					player.sleep()
					player.saveTime()

				# with open(resumeDB, 'rb') as dic:
					# videoData = pickle.load(dic)

				# if player.videoWatched:
					# del videoData[filename]
				# else:
					# videoData[filename] = player.time

				# with open(resumeDB, 'wb+') as dic:
					# pickle.dump(videoData, dic)

		# if dbType == 'movie':
			# xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.RefreshMovie", "params": {"movieid":' + str(dbID) + ', "ignorenfo": true}, "id": "1"}')
		# elif dbType == 'episode':
			# xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.RefreshEpisode", "params": {"episodeid":' + str(dbID) + ', "ignorenfo": true}, "id": "1"}')

		# request = {"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "filter": {"field": "playcount", "operator": "greaterthan", "value": "0"}, "limits": { "start": 0 }, "properties": ["playcount"], "sort": { "order": "ascending", "method": "label" } }, "id": "libMovies"}
		# request = {"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "filter": {"field": "playcount", "operator": "greaterthan", "value": "0"}, "limits": { "start": 0 }, "properties": ["playcount"], "sort": { "order": "ascending", "method": "label" } }, "id": "libMovies"}

		xbmcplugin.endOfDirectory(self.plugin_handle)
		return
