import os
import re
import urllib
import datetime
from threading import Thread
from socketserver import ThreadingMixIn
from http.server import BaseHTTPRequestHandler, HTTPServer

import xbmc
import xbmcgui
import xbmcaddon

import constants
from .. import sync
from .. import accounts
from .. import playback
from .. import encryption
from .. import filesystem
from .. import google_api
from . import registration


class ServerRunner(Thread):

	def __init__(self):
		super().__init__()

	def run(self):
		self._server = ThreadedHTTPServer(("", constants.settings.getSettingInt("server_port", 8011)), ServerHandler)
		self._server.daemon_threads = True

		try:
			self._server.serve_forever()
		except Exception:
			self.shutdown()
			self.server_close()

	def shutdown(self):
		self._server.shutdown()
		self._server.server_close()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):

	def __init__(self, *args, **kwargs):
		HTTPServer.__init__(self, *args, **kwargs)
		self.shutdownRequest = False
		self.settings = constants.settings
		self.monitor = xbmc.Monitor()
		self.accountManager = accounts.manager.AccountManager(self.settings)
		self.cloudService = google_api.drive.GoogleDrive()
		self.cache = sync.cache.Cache()
		self.taskManager = sync.tasker.Tasker(self.settings, self.accountManager)
		self.taskManager.run()
		self.fileOperations = filesystem.operations.FileOperations()
		self.gDriveIconPath = os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "media", "icon.png")

class ServerHandler(BaseHTTPRequestHandler):

	def do_POST(self):

		if self.path == "/play_url":
			self.server.failed = False
			contentLength = int(self.headers["Content-Length"]) # <--- Gets the size of data
			postData = self.rfile.read(contentLength).decode("utf-8") # <--- Gets the data itself
			encrypted, self.server.url, self.server.driveID, self.server.fileID, self.server.transcoded = re.findall("encrypted=(.*)&url=(.*)&drive_id=(.*)&file_id=(.*)&transcoded=(.*)", postData)[0]

			if encrypted == "True":
				self.server.encrypted = True
			else:
				self.server.encrypted = False

			if self.server.transcoded == "False":
				self.server.transcoded = False

			self.server.accountManager.loadAccounts()
			account = self.server.accountManager.getAccount(self.server.driveID)
			self.server.cloudService.setAccount(account)
			self.send_response(200)
			self.end_headers()

		elif self.path == "/start_player":
			contentLength = int(self.headers["Content-Length"])
			postData = self.rfile.read(contentLength).decode("utf-8")
			self.send_response(200)
			self.end_headers()
			dbID, dbType = re.findall("db_id=(.*)&db_type=(.*)", postData)[0]

			if dbID == "False":
				dbID = False
				dbType = False
				trackProgress = False
			else:
				trackProgress = True

			player = playback.player.Player(dbID, dbType, trackProgress)

			while not self.server.monitor.abortRequested() and not player.close:

				if datetime.datetime.now() >= self.server.cloudService.account.expiry:

					self.server.cloudService.refreshToken()

					if self.server.transcoded:
						self.server.url = self.server.cloudService.getStreams(self.server.fileID, (self.server.transcoded,))[1]

				if self.server.monitor.waitForAbort(1):
					break

		elif self.path == "/set_alias":
			contentLength = int(self.headers["Content-Length"])
			postData = self.rfile.read(contentLength).decode("utf-8")
			self.send_response(200)
			self.end_headers()
			driveID, alias = re.findall("drive_id=(.*)&alias=(.*)", postData)[0]
			self.server.accountManager.setAlias(driveID, alias)
			driveSettings = self.server.cache.getDrive(driveID)

			if not driveSettings:
				xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
				xbmc.executebuiltin("Container.Refresh")
				return

			syncRootPath = self.server.cache.getSyncRootPath()
			drivePathOld = os.path.join(syncRootPath, driveSettings["local_path"])
			drivePathNew = os.path.join(syncRootPath, alias)
			self.server.cache.updateDrive({"local_path": alias}, driveID)
			self.server.fileOperations.renameFolder(syncRootPath, drivePathOld, drivePathNew)
			xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
			xbmc.executebuiltin("Container.Refresh")

		elif self.path == "/delete_drive":
			contentLength = int(self.headers["Content-Length"])
			postData = self.rfile.read(contentLength).decode("utf-8")
			self.send_response(200)
			self.end_headers()
			driveID = re.findall("drive_id=(.*)", postData)[0]
			self.server.taskManager.removeTask(driveID)
			self.server.cache.deleteDrive(driveID)
			self.server.accountManager.deleteDrive(driveID)
			xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
			xbmc.executebuiltin("Container.Refresh")

		elif self.path == "/add_sync_task":
			contentLength = int(self.headers["Content-Length"])
			postData = self.rfile.read(contentLength).decode("utf-8")
			self.send_response(200)
			self.end_headers()
			driveID, folderID, folderName = re.findall("drive_id=(.*)&folder_id=(.*)&folder_name=(.*)", postData)[0]
			self.server.taskManager.activeTasks.append(driveID)
			self.server.taskManager.createTask(driveID, folderID, folderName)
			self.server.taskManager.activeTasks.remove(driveID)

		elif self.path == "/register":
			contentLength = int(self.headers["Content-Length"]) # <--- Gets the size of data
			postData = self.rfile.read(contentLength).decode("utf-8") # <--- Gets the data itself
			accountName, clientID, clientSecret = re.findall("account=(.*)&client_id=(.*)&client_secret=(.*)", postData)[0]
			authURL = self.server.cloudService.getAuthURL(clientID, self.server.server_port)
			self.server.account = accounts.account.Account()
			self.server.account.name = urllib.parse.unquote_plus(accountName)
			self.server.account.clientID = clientID
			self.server.account.clientSecret = clientSecret
			self.send_response(303)
			self.send_header("Location", authURL)
			self.end_headers()

		elif self.path == "/stop_folder_sync":
			contentLength = int(self.headers["Content-Length"])
			postData = self.rfile.read(contentLength).decode("utf-8")
			self.send_response(200)
			self.end_headers()
			folderID, delete = re.findall("folder_id=(.*)&delete=(.*)", postData)[0]
			delete = True if delete == "True" else False
			self.server.cache.removeFolder(folderID, deleteFiles=delete)

			if delete:
				xbmcgui.Dialog().notification(
					self.server.settings.getLocalizedString(30000), 
					self.server.settings.getLocalizedString(30045),
					self.server.gDriveIconPath,
				)

		elif self.path == "/stop_all_folders_sync":
			contentLength = int(self.headers["Content-Length"])
			postData = self.rfile.read(contentLength).decode("utf-8")
			self.send_response(200)
			self.end_headers()
			driveID, delete = re.findall("drive_id=(.*)&delete=(.*)", postData)[0]
			delete = True if delete == "True" else False
			self.server.cache.removeAllFolders(driveID, deleteFiles=delete)

			if delete:
				xbmcgui.Dialog().notification(
					self.server.settings.getLocalizedString(30000),
					self.server.settings.getLocalizedString(30045),
					self.server.gDriveIconPath,
				)

		elif self.path == "/renew_task":
			contentLength = int(self.headers["Content-Length"])
			postData = self.rfile.read(contentLength).decode("utf-8")
			self.send_response(200)
			self.end_headers()
			driveID = re.findall("drive_id=(.*)", postData)[0]
			self.server.taskManager.removeTask(driveID)
			self.server.taskManager.spawnTask(self.server.cache.getDrive(driveID), startUpRun=False)

		elif self.path == "/force_sync":
			contentLength = int(self.headers["Content-Length"])
			postData = self.rfile.read(contentLength).decode("utf-8")
			self.send_response(200)
			self.end_headers()
			driveID = re.findall("drive_id=(.*)", postData)[0]
			self.server.taskManager.sync(driveID)

	def do_HEAD(self):

		if self.path == "/play":
			req = urllib.request.Request(self.server.url, headers=self.server.cloudService.getHeaders())
			req.get_method = lambda: "HEAD"

			try:
				response = urllib.request.urlopen(req)
			except urllib.error.URLError as e:
				self.server.failed = True

				if e.code == 404:
					xbmcgui.Dialog().ok(self.server.settings.getLocalizedString(30003), self.server.settings.getLocalizedString(30209))
					return

				elif e.code == 401:
					xbmcgui.Dialog().ok(self.server.settings.getLocalizedString(30003), self.server.settings.getLocalizedString(30018))
					return

				elif e.code == 403 or e.code == 429:
					accountChange = False
					accounts = self.server.accountManager.getAccounts(self.server.driveID)

					for account in accounts[1:]:
						self.server.cloudService.setAccount(account)
						tokenRefresh = self.server.cloudService.refreshToken()

						if tokenRefresh == "failed":
							continue

						if self.server.transcoded:
							self.server.url = self.server.cloudService.getStreams(self.server.fileID, (self.server.transcoded,))[1]

						req = urllib.request.Request(self.server.url, headers=self.server.cloudService.getHeaders())
						req.get_method = lambda: "HEAD"

						try:
							response = urllib.request.urlopen(req)
						except urllib.error.URLError:
							continue

						accountChange = True
						xbmcgui.Dialog().notification(
							f"{self.server.settings.getLocalizedString(30003)}: {self.server.settings.getLocalizedString(30006)}",
							self.server.settings.getLocalizedString(30007),
							self.server.gDriveIconPath,
						)
						break

					if not accountChange:
						xbmcgui.Dialog().ok(
							f"{self.server.settings.getLocalizedString(30003)}: {self.server.settings.getLocalizedString(30006)}",
							self.server.settings.getLocalizedString(30009),
						)
						return
					else:
						accounts.remove(account)
						accounts.insert(0, account)
						self.server.accountManager.saveAccounts()

				else:
					xbmc.log("gdrive error: " + str(e))
					return

			self.server.failed = False
			self.send_response(200)

			self.send_header("Content-Type", response.info().get("Content-Type"))
			self.send_header("Content-Length", response.info().get("Content-Length"))
			self.send_header("Cache-Control", response.info().get("Cache-Control"))
			self.send_header("Date", response.info().get("Date"))
			self.send_header("Content-type", "video/mp4")
			self.send_header("Accept-Ranges", "bytes")
			# self.send_header("ETag", response.info().get("ETag"))
			# self.send_header("Server", response.info().get("Server"))

			self.end_headers()
			# may want to add more granular control over chunk fetches
			# self.wfile.write(response.read())
			response.close()
			self.server.length = response.info().get("Content-Length")

	def do_GET(self):

		if self.path == "/play":

			if self.server.failed:
				return

			start, end = re.findall("([\d]+)-([\d]*)", self.headers["range"])[0]
			start = int(start) if start else ""
			end = int(end) if end else ""
			startOffset = 0

			if self.server.encrypted and start != "" and start > 16 and end == "":
				# start = start - (16 - (end % 16))
				xbmc.log("START = " + str(start))
				startOffset = 16 - ((int(self.server.length) - start) % 16) + 8

			# if start == 23474184:
				# start = start - (16 - (end % 16))
				# start = 23474184 - 8

			xbmc.log("GET " + self.server.url + "\n" + self.server.cloudService.getHeadersEncoded() + "\n")

			if start == "":
				req = urllib.request.Request(self.server.url, headers=self.server.cloudService.getHeaders())
			else:
				req = urllib.request.Request(
					self.server.url,
					headers=self.server.cloudService.getHeaders(
						additionalHeader="Range",
						additionalValue=f"bytes={start - startOffset}-{end}",
					)
				)

			try:
				response = urllib.request.urlopen(req)
			except urllib.error.URLError as e:
				xbmc.log("gdrive error: " + str(e))
				return

			if start == "":
				self.send_response(200)
				self.send_header("Content-Length", response.info().get("Content-Length"))
			else:
				self.send_response(206)
				self.send_header("Content-Length", str(int(response.info().get("Content-Length")) - startOffset))
				# self.send_header("Content-Range", "bytes " + str(start) + "-" + str(end))

				if not end:
					self.send_header("Content-Range", f"bytes {start}-{int(self.server.length) - 1}/{self.server.length}")
				else:
					self.send_header("Content-Range", f"bytes {start}-{end}/{self.server.length}")

				# self.send_header("Content-Range", response.info().get("Content-Range"))
				xbmc.log(f"Content-Range!!!{start}-{int(self.server.length) - 1}/{self.server.length}\n")

			xbmc.log(str(response.info()) + "\n")

			self.send_header("Content-Type", response.info().get("Content-Type"))
			# self.send_header("Content-Length", response.info().get("Content-Length"))
			self.send_header("Cache-Control", response.info().get("Cache-Control"))
			self.send_header("Date", response.info().get("Date"))
			self.send_header("Content-type", "video/mp4")
			self.send_header("Accept-Ranges", "bytes")

			self.end_headers()
			# may want to add more granular control over chunk fetches
			# self.wfile.write(response.read())

			if self.server.encrypted:
				decrypt = encryption.encrypter.Encrypter(self.server.settings.getSetting("crypto_salt"), self.server.settings.getSetting("crypto_password"))

				try:
					decrypt.decryptStreamChunkOld(response, self.wfile, startOffset=startOffset)
				except Exception as e:
					xbmc.log(str(e))

			else:
				CHUNK = 16 * 1024

				try:

					while True:
						chunk = response.read(CHUNK)

						if not chunk:
							break

						self.wfile.write(chunk)

				except Exception as e:
					xbmc.log(str(e))

			response.close()

		elif self.path == "/force_sync_all":
			self.send_response(200)
			self.end_headers()
			self.server.taskManager.syncAll()

		elif self.path == "/register":
			self.send_response(200)
			self.end_headers()
			data = registration.form
			self.wfile.write(data.encode("utf-8"))

		elif "/status" in self.path:

			try:
				code = re.findall("code=(.*)&", self.path)[0]
				token = self.server.cloudService.getToken(self.server.account.clientID, self.server.account.clientSecret, code, self.server.server_port)
				self.server.account.accessToken = token["access_token"]
				self.server.account.refreshToken = token["refresh_token"]
				self.server.cloudService.setAccount(self.server.account)
				self.server.cloudService.refreshToken()
				driveID = self.server.cloudService.getDriveID()
				self.server.accountManager.loadAccounts()
				self.server.accountManager.addAccount(
					self.server.account,
					driveID,
				)
				redirect = "/registration_succeeded"
			except Exception:
				redirect = "/registration_failed"

			self.send_response(303)
			self.send_header("Location", f"http://localhost:{self.server.server_port}{redirect}")
			self.end_headers()

		elif self.path == "/registration_succeeded":
			self.send_response(200)
			self.end_headers()
			data = registration.status(self.server.settings.getLocalizedString(30046))
			self.wfile.write(data.encode("utf-8"))
			xbmc.executebuiltin("Dialog.Close(all,true)")
			xbmc.executebuiltin("Container.Refresh")

		elif self.path == "/registration_failed":
			self.send_response(200)
			self.end_headers()
			data = registration.status(self.server.settings.getLocalizedString(30047))
			self.wfile.write(data.encode("utf-8"))
