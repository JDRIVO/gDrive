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
import urllib2
import xbmc
import xbmcgui
import constants
from threading import Thread
from SocketServer import ThreadingMixIn
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from resources.lib import encryption, enrolment, gplayer


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
	"""Handle requests in a separate thread."""


class MyHTTPServer(ThreadingMixIn, HTTPServer):

	def __init__(self, *args, **kwargs):
		HTTPServer.__init__(self, *args, **kwargs)

	def setDetails(self, PLUGIN_HANDLE, PLUGIN_NAME, PLUGIN_URL, settings):
		self.PLUGIN_HANDLE = PLUGIN_HANDLE
		self.PLUGIN_NAME = PLUGIN_NAME
		self.PLUGIN_URL = PLUGIN_URL
		self.settings = settings
		self.userAgent = self.settings.getSetting("user_agent")
		self.close = False

	def run(self):

		try:
			self.serve_forever()
		except:
			self.close = True
			# Clean-up server (close socket, etc.)
			self.server_close()

	def startGPlayer(self, dbID, dbType, widget, trackProgress):
		lastUpdate = time.time()
		player = gplayer.GPlayer(dbID=dbID, dbType=dbType, widget=int(widget), trackProgress=int(trackProgress), settings=self.settings)

		while not player.close and not self.close:

			if time.time() - lastUpdate >= 1740:
				lastUpdate = time.time()
				self.service.refreshToken()

			xbmc.sleep(1000)

class MyStreamer(BaseHTTPRequestHandler):

	# Handler for the GET requests
	def do_POST(self):
		# debug - print headers in log
		headers = str(self.headers)
		print(headers)

		if self.path == "/crypto_playurl":
			contentLength = int(self.headers["Content-Length"]) # <--- Gets the size of data
			postData = self.rfile.read(contentLength).decode("utf-8") # <--- Gets the data itself

			for r in re.finditer("instance\=([^\&]+)\&url\=([^\|]+)", postData, re.DOTALL):
				instanceName, url = r.groups()
				xbmc.log("url = " + url + "\n")
				cloudservice2 = constants.cloudservice2
				self.server.service = cloudservice2(
					self.server.PLUGIN_HANDLE,
					self.server.PLUGIN_URL,
					self.server.settings,
					instanceName,
					self.server.userAgent,
				)
				self.server.playbackURL = url

			self.server.service.refreshToken()
			self.send_response(200)
			self.end_headers()

		elif self.path == "/start_gplayer":
			contentLength = int(self.headers["Content-Length"])
			postData = self.rfile.read(contentLength).decode("utf-8")
			self.send_response(200)
			self.end_headers()

			for r in re.finditer("dbid\=([^\&]+)\&dbtype\=([^\|]+)\&widget\=([^\|]+)\&track\=([^\|]+)", postData, re.DOTALL):
				dbID, dbType, widget, trackProgress = r.groups()

			Thread(target=self.server.startGPlayer, args=(dbID, dbType, widget, trackProgress)).start()

		# redirect url to output
		elif self.path == "/enroll?default=false":
			contentLength = int(self.headers["Content-Length"])  # <--- Gets the size of data
			postData = self.rfile.read(contentLength).decode("utf-8")  # <--- Gets the data itself
			self.send_response(200)
			self.end_headers()

			for r in re.finditer("client_id=([^&]+)&client_secret=([^&]+)", postData, re.DOTALL):
				clientID, clientSecret = r.groups()
				data = enrolment.page2(clientID, clientSecret)
				self.wfile.write(data.encode("utf-8"))

		# redirect url to output
		elif self.path == "/enroll":
			contentLength = int(self.headers["Content-Length"])  # <--- Gets the size of data
			postData = self.rfile.read(contentLength).decode("utf-8")  # <--- Gets the data itself
			self.send_response(200)
			self.end_headers()

			for r in re.finditer("account=([^&]+)&code=([^&]+)&client_id=([^&]+)&client_secret=([^&]+)", postData, re.DOTALL):
				account, code, clientID, clientSecret = r.groups()
				code = code.replace("%2F", "/")
				count = 1

				while True:
					instanceName = self.server.PLUGIN_NAME + str(count)

					try:
						username = self.server.settings.getSetting(instanceName + "_username")
					except:
						username = False

					if not username or username == account:
						self.server.settings.setSetting(instanceName + "_username", account)
						self.server.settings.setSetting(instanceName + "_code", code)
						self.server.settings.setSetting(instanceName + "_client_id", clientID)
						self.server.settings.setSetting(instanceName + "_client_secret", clientSecret)

						if not self.server.settings.getSetting("default_account"):
							self.server.settings.setSetting("default_account", str(count))
							self.server.settings.setSetting("default_account_ui", account)

						if count > self.server.settings.getSettingInt("account_amount"):
							self.server.settings.setSettingInt("account_amount", count)

						break

					count += 1

				url = "https://accounts.google.com/o/oauth2/token"
				header = {"User-Agent": self.server.userAgent, "Content-Type": "application/x-www-form-urlencoded"}
				url = "https://accounts.google.com/o/oauth2/token"
				data = "code={}&client_id={}&client_secret={}&redirect_uri=urn:ietf:wg:oauth:2.0:oob&grant_type=authorization_code".format(
					code, clientID, clientSecret
				)
				req = urllib2.Request(url, data.encode("utf-8"), header)

				# try login
				try:
					response = urllib2.urlopen(req)
				except urllib2.URLError as e:
					self.send_response(200)
					self.end_headers()
					self.wfile.write(str(e).encode("utf-8"))
					return

				responseData = response.read().decode("utf-8")
				response.close()

				# retrieve authorization token
				for r in re.finditer('\"access_token\"\s?\:\s?\"([^\"]+)\".+?' + '\"refresh_token\"\s?\:\s?\"([^\"]+)\".+?', responseData, re.DOTALL):
					accessToken, refreshToken = r.groups()
					self.server.settings.setSetting(instanceName + "_auth_access_token", accessToken)
					self.server.settings.setSetting(instanceName + "_auth_refresh_token", refreshToken)
					self.wfile.write(b"Successfully enrolled account.")

				for r in re.finditer('\"error_description\"\s?\:\s?\"([^\"]+)\"', responseData, re.DOTALL):
					errorMessage = r.group(1)
					self.wfile.write(errorMessage.encode("utf-8"))

				return

	def do_HEAD(self):
		# debug - print headers in log
		headers = str(self.headers)
		print(headers)

		# redirect url to output
		if self.path == "/play":
			url = self.server.playbackURL
			xbmc.log("HEAD " + url + "\n")
			req = urllib2.Request(url, None, self.server.service.getHeadersList())
			req.get_method = lambda: "HEAD"

			try:
				response = urllib2.urlopen(req)
			except urllib2.URLError as e:

				if e.code == 404:
					xbmcgui.Dialog().ok(self.server.settings.getLocalizedString(30003), self.server.settings.getLocalizedString(30209))
					return
				elif e.code == 401:
					xbmc.log("ERROR\n" + self.server.service.getHeadersEncoded())
					xbmcgui.Dialog().ok(self.server.settings.getLocalizedString(30003), self.server.settings.getLocalizedString(30018))
					return
				elif e.code == 403 or e.code == 429:
					xbmc.log("ERROR\n" + self.server.service.getHeadersEncoded())

					if not self.server.settings.getSetting("fallback"):
						xbmcgui.Dialog().ok(
							self.server.settings.getLocalizedString(30003) + ": " + self.server.settings.getLocalizedString(30006),
							self.server.settings.getLocalizedString(30009),
						)
						return

					fallbackAccounts = self.server.settings.getSetting("fallback_accounts").split(",")
					defaultAccount = self.server.settings.getSetting("default_account")
					accountChange = False

					for fallbackAccount in fallbackAccounts:
						username = self.server.settings.getSetting("gdrive{}_username".format(fallbackAccount))

						if not username:
							fallbackAccounts.remove(fallbackAccount)
							continue

						try:
							cloudservice2 = constants.cloudservice2
							self.server.service = cloudservice2(
								self.server.PLUGIN_HANDLE,
								self.server.PLUGIN_URL,
								self.server.settings,
								"gdrive" + fallbackAccount,
								self.server.userAgent,
							)
							self.server.service.refreshToken()

							req = urllib2.Request(url, None, self.server.service.getHeadersList())
							req.get_method = lambda: "HEAD"
							response = urllib2.urlopen(req)

							if not defaultAccount in fallbackAccounts:
								fallbackAccounts.append(defaultAccount)

							fallbackAccounts.remove(fallbackAccount)
							self.server.settings.setSetting("default_account", fallbackAccount)
							self.server.settings.setSetting("default_account_ui", username)
							accountChange = True
							xbmcgui.Dialog().notification(
								self.server.settings.getLocalizedString(30003) + ": " + self.server.settings.getLocalizedString(30006),
								self.server.settings.getLocalizedString(30007),
							)
							break

						except:
							continue

					self.server.settings.setSetting("fallback_accounts", ",".join(fallbackAccounts))
					self.server.settings.setSetting(
						"fallback_accounts_ui",
						", ".join(
							self.server.settings.getSetting("gdrive{}_username".format(x))
							for x in fallbackAccounts
						)
					)

					if not accountChange:
						xbmcgui.Dialog().ok(
							self.server.settings.getLocalizedString(30003) + ": " + self.server.settings.getLocalizedString(30006),
							self.server.settings.getLocalizedString(30009),
						)
						return

				else:
					return

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

			## may want to add more granular control over chunk fetches
			# self.wfile.write(response.read())

			response.close()
			xbmc.log("DONE")
			self.server.length = response.info().get("Content-Length")

	# Handler for the GET requests
	def do_GET(self):
		# debug - print headers in log
		headers = str(self.headers)
		print(headers)

		start = end = ""
		startOffset = 0

		for r in re.finditer("Range\:\s+bytes\=(\d+)\-", headers, re.DOTALL):
			start = int(r.group(1))
			break

		for r in re.finditer("Range\:\s+bytes\=\d+\-(\d+)", headers, re.DOTALL):
			end = int(r.group(1))
			break

		# redirect url to output
		if self.path == "/play":

			if start != "" and start > 16 and end == "":
				# start = start - (16 - (end % 16))
				xbmc.log("START = " + str(start))
				startOffset = 16 - ((int(self.server.length) - start) % 16) + 8

			# if start == 23474184:
				# start = start - (16 - (end % 16))
				# start = 23474184 - 8

			url = self.server.playbackURL
			xbmc.log("GET " + url + "\n" + self.server.service.getHeadersEncoded() + "\n")

			if start == "":
				req = urllib2.Request(url, None, self.server.service.getHeadersList())
			else:
				req = urllib2.Request(
					url,
					None,
					self.server.service.getHeadersList(
						additionalHeader="Range",
						additionalValue="bytes=" + str(start - startOffset) + "-" + str(end),
					)
				)

			try:
				response = urllib2.urlopen(req)
			except urllib2.URLError as e:

				if e.code == 403 or e.code == 401:
					xbmc.log("ERROR\n" + self.server.service.getHeadersEncoded())
					self.server.service.refreshToken()
					req = urllib2.Request(url, None, self.server.service.getHeadersList())

					try:
						response = urllib2.urlopen(req)
					except:
						xbmc.log("STILL ERROR\n" + self.server.service.getHeadersEncoded())
						return

				else:
					return

			if start == "":
				self.send_response(200)
				self.send_header("Content-Length", response.info().get("Content-Length"))
			else:
				self.send_response(206)
				self.send_header("Content-Length", str(int(response.info().get("Content-Length")) - startOffset))
				# self.send_header("Content-Range", "bytes " + str(start) + "-" + str(end))

				if end == "":
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

			decrypt = encryption.Encryption(self.server.settings.getSetting("crypto_salt"), self.server.settings.getSetting("crypto_password"))
			decrypt.decryptStreamChunkOld(response, self.wfile, startOffset=startOffset)

			response.close()

		# redirect url to output
		elif self.path == "/enroll":
			self.send_response(200)
			self.end_headers()
			self.wfile.write(enrolment.page1)
			return
