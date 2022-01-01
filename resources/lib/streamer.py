"""
	Copyright (C) 2014-2016 ddurdle

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


"""

import re
import time
import urllib
import urllib2
from threading import Thread
from SocketServer import ThreadingMixIn
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

import xbmc
import xbmcgui

from . import account_manager, encryption, enrolment, gdrive_api, player


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
	"""Handle requests in a separate thread."""


class MyHTTPServer(ThreadingMixIn, HTTPServer):

	def __init__(self, *args, **kwargs):
		self.settings = kwargs["settings"]
		port = self.settings.getSettingInt("server_port", 8011)
		HTTPServer.__init__(self, ("", port), MyStreamer)

		self.monitor = xbmc.Monitor()
		self.accountManager = account_manager.AccountManager(self.settings)
		self.cloudService = gdrive_api.GoogleDrive()

	def run(self):

		try:
			self.serve_forever()
		except:
			self.server_close()

	def startPlayer(self, dbID, dbType, widget, trackProgress):
		lastUpdate = time.time()
		vPlayer = player.Player(dbID=dbID, dbType=dbType, widget=int(widget), trackProgress=int(trackProgress), settings=self.settings)
		expiry = self.cloudService.account["expiry"] - 30

		while not self.monitor.abortRequested() and not vPlayer.close:

			if time.time() - lastUpdate >= expiry:
				lastUpdate = time.time()
				self.cloudService.refreshToken()

				if self.transcoded:
					self.playbackURL = self.cloudService.getStreams(self.fileID, self.transcoded)

			if self.monitor.waitForAbort(1):
				break


class MyStreamer(BaseHTTPRequestHandler):

	def do_POST(self):

		if self.path == "/play_url":
			contentLength = int(self.headers["Content-Length"]) # <--- Gets the size of data
			postData = self.rfile.read(contentLength).decode("utf-8") # <--- Gets the data itself
			encrypted, accountNumber, url, transcoded, fileID = re.findall("encrypted=(.*)&account=(.*)&url=(.*)&transcoded=(.*)&fileid=(.*)", postData)[0]
			self.server.accountManager.loadAccounts()
			self.server.cloudService.setAccount(self.server.accountManager.accounts[accountNumber])

			if encrypted == "True":
				self.server.crypto = True
			else:
				self.server.crypto = False

			if transcoded == "False":
				self.server.transcoded = False
			else:
				self.server.transcoded = transcoded
				self.server.fileID = fileID

			self.server.playbackURL = url
			self.send_response(200)
			self.end_headers()

		elif self.path == "/start_player":
			contentLength = int(self.headers["Content-Length"])
			postData = self.rfile.read(contentLength).decode("utf-8")
			self.send_response(200)

			self.end_headers()
			dbID, dbType, widget, trackProgress = re.findall("dbid=([\d]+)&dbtype=(.*)&widget=(\d)&track=(\d)", postData)[0]
			Thread(target=self.server.startPlayer, args=(dbID, dbType, widget, trackProgress)).start()

		elif self.path == "/enroll?default=false":
			contentLength = int(self.headers["Content-Length"]) # <--- Gets the size of data
			postData = self.rfile.read(contentLength).decode("utf-8") # <--- Gets the data itself
			self.send_response(200)
			self.end_headers()

			clientID, clientSecret = re.findall("client_id=(.*)&client_secret=(.*)", postData)[0]
			data = enrolment.form2(clientID, clientSecret)
			self.wfile.write(data.encode("utf-8"))

		elif self.path == "/enroll":
			contentLength = int(self.headers["Content-Length"]) # <--- Gets the size of data
			postData = self.rfile.read(contentLength).decode("utf-8") # <--- Gets the data itself
			postData = urllib.unquote_plus(postData)
			self.send_response(200)

			self.end_headers()
			accountName, code, clientID, clientSecret = re.findall("account=(.*)&code=(.*)&client_id=(.*)&client_secret=(.*)", postData)[0]
			refreshToken = self.server.cloudService.getToken(code, clientID, clientSecret)

			if "failed" in refreshToken:
				data = enrolment.status(refreshToken[1])
				self.wfile.write(data.encode("utf-8"))
				return

			self.server.accountManager.loadAccounts()
			accountNumber = self.server.accountManager.addAccount(
				{
					"username": accountName,
					"code": code,
					"client_id": clientID,
					"client_secret": clientSecret,
					"refresh_token": refreshToken,
				}
			)
			defaultAccountName, defaultAccountNumber = self.server.accountManager.getDefaultAccount()

			if not defaultAccountName:
				self.server.accountManager.setDefaultAccount(accountName, accountNumber)

			data = enrolment.status("Successfully enrolled account")
			self.wfile.write(data.encode("utf-8"))

	def do_HEAD(self):

		if self.path == "/play":
			url = self.server.playbackURL
			req = urllib2.Request(url, headers=self.server.cloudService.getHeaders())
			req.get_method = lambda: "HEAD"

			try:
				response = urllib2.urlopen(req)
			except urllib2.URLError as e:
				self.server.failed = True

				if e.code == 404:
					xbmcgui.Dialog().ok(self.server.settings.getLocalizedString(30003), self.server.settings.getLocalizedString(30209))
					return

				elif e.code == 401:
					xbmcgui.Dialog().ok(self.server.settings.getLocalizedString(30003), self.server.settings.getLocalizedString(30018))
					return

				elif e.code == 403 or e.code == 429:

					if not self.server.settings.getSetting("fallback"):
						xbmcgui.Dialog().ok(
							self.server.settings.getLocalizedString(30003) + ": " + self.server.settings.getLocalizedString(30006),
							self.server.settings.getLocalizedString(30009),
						)
						return

					fallbackAccountNames, fallbackAccountNumbers = self.server.accountManager.getFallbackAccounts()
					defaultAccountName, defaultAccountNumber = self.server.accountManager.getDefaultAccount()
					accountChange = False

					for fallbackAccountName, fallbackAccountNumber in list(zip(fallbackAccountNames, fallbackAccountNumbers)):
						self.server.cloudService.setAccount(self.server.accountManager.accounts[fallbackAccountNumber])
						refreshToken = self.server.cloudService.refreshToken()

						if refreshToken == "failed":
							continue

						req = urllib2.Request(url, headers=self.server.cloudService.getHeaders())
						req.get_method = lambda: "HEAD"

						try:
							response = urllib2.urlopen(req)
						except urllib2.URLError as e:
							continue

						if not defaultAccountNumber in fallbackAccountNumbers:
							fallbackAccountNames.append(defaultAccountName)
							fallbackAccountNumbers.append(defaultAccountNumber)

						fallbackAccountNames.remove(fallbackAccountName)
						fallbackAccountNumbers.remove(fallbackAccountNumber)
						self.server.accountManager.setDefaultAccount(fallbackAccountName, fallbackAccountNumber)

						xbmcgui.Dialog().notification(
							self.server.settings.getLocalizedString(30003) + ": " + self.server.settings.getLocalizedString(30006),
							self.server.settings.getLocalizedString(30007),
						)
						accountChange = True
						break

					self.server.accountManager.setFallbackAccounts(fallbackAccountNames, fallbackAccountNumbers)

					if not accountChange:
						xbmcgui.Dialog().ok(
							self.server.settings.getLocalizedString(30003) + ": " + self.server.settings.getLocalizedString(30006),
							self.server.settings.getLocalizedString(30009),
						)
						return

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

			if self.server.crypto and start != "" and start > 16 and end == "":
				# start = start - (16 - (end % 16))
				xbmc.log("START = " + str(start))
				startOffset = 16 - ((int(self.server.length) - start) % 16) + 8

			# if start == 23474184:
				# start = start - (16 - (end % 16))
				# start = 23474184 - 8

			url = self.server.playbackURL
			xbmc.log("GET " + url + "\n" + self.server.cloudService.getHeadersEncoded() + "\n")

			if start == "":
				req = urllib2.Request(url, headers=self.server.cloudService.getHeaders())
			else:
				req = urllib2.Request(
					url,
					headers=self.server.cloudService.getHeaders(
						additionalHeader="Range",
						additionalValue="bytes=" + str(start - startOffset) + "-" + str(end),
					)
				)

			try:
				response = urllib2.urlopen(req)
			except urllib2.URLError as e:
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
					self.send_header("Content-Range", "bytes {}-{}/{}".format(start, int(self.server.length) - 1, self.server.length))
				else:
					self.send_header("Content-Range", "bytes {}-{}/{}".format(start, end, self.server.length))

				# self.send_header("Content-Range", response.info().get("Content-Range"))
				xbmc.log("Content-Range!!!{}-{}/{}\n".format(start, int(self.server.length) - 1, self.server.length))

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

			if self.server.crypto:
				decrypt = encryption.Encryption(self.server.settings.getSetting("crypto_salt"), self.server.settings.getSetting("crypto_password"))

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

		elif self.path == "/enroll":
			self.send_response(200)
			self.end_headers()
			data = enrolment.form1
			self.wfile.write(data.encode("utf-8"))
