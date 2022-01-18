import re
import json
import datetime
import urllib.error
import urllib.parse
import urllib.request

import xbmc

from . import encryption

API_VERSION = "3"
GDRIVE_URL = "https://www.googleapis.com/drive/v3"
GOOGLE_AUTH_URL = "https://oauth2.googleapis.com/token"
SCOPE_URL = "https://www.googleapis.com/auth/drive.readonly"
USER_AGENT = "Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/532.0 (KHTML, like Gecko) Chrome/3.0.195.38 Safari/532.0"
HEADERS = {"User-Agent": USER_AGENT}
HEADERS_FORM_ENCODED = {
	"User-Agent": USER_AGENT,
	"Content-Type": "application/x-www-form-urlencoded",
}

API = {
	"changes": GDRIVE_URL + "/changes",
	"drives": GDRIVE_URL + "/drives",
	"files": GDRIVE_URL + "/files",
}


class GoogleDrive:

	def __init__(self, accountManager):
		self.accountManager = accountManager

	def setAccount(self, account):
		self.account = account

	@staticmethod
	def constructDriveURL(fileID):
		params = {
			"q": "supportsAllDrives=true",
			"alt": "media",
		}
		return "{}/{}?{}".format(
			API["files"],
			fileID,
			urllib.parse.urlencode(params),
		)

	def sendPayload(self, url, data=None, headers=HEADERS, cookie=None, download=False):

		if data:
			data = data.encode("utf8")

		req = urllib.request.Request(url, data, headers)

		try:
			response = urllib.request.urlopen(req)
		except urllib.error.URLError as e:
			xbmc.log("gdrive error: " + str(e))
			return {"failed": str(e)}

		responseData = response.read()

		if download:
			return responseData

		responseData = responseData.decode("utf-8")
		if cookie: cookie = response.headers["set-cookie"]
		response.close()

		try:
			responseData = json.loads(responseData)
		except:
			pass

		if not cookie:
			return responseData
		else:
			return responseData, cookie

	def getToken(self, code, clientID, clientSecret):
		data = "code={}&client_id={}&client_secret={}&redirect_uri=urn:ietf:wg:oauth:2.0:oob&grant_type=authorization_code".format(
			code, clientID, clientSecret
		)
		response = self.sendPayload(GOOGLE_AUTH_URL, data, HEADERS_FORM_ENCODED)

		if "failed" in response:
			return response

		return response["refresh_token"]

	def refreshToken(self):
		key = self.account.get("key")

		if key:
			jwt = encryption.JasonWebToken(self.account["email"], key, SCOPE_URL, GOOGLE_AUTH_URL).create()
			data = "grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=" + jwt
		else:
			data = "client_id={}&client_secret={}&refresh_token={}&grant_type=refresh_token".format(
				self.account["client_id"], self.account["client_secret"], self.account["refresh_token"]
			)

		response = self.sendPayload(GOOGLE_AUTH_URL, data, HEADERS_FORM_ENCODED)

		if "failed" in response:
			return "failed"

		self.account["access_token"] = response["access_token"].rstrip(".")
		expiry = datetime.datetime.now() + datetime.timedelta(seconds=response["expires_in"] - 600)
		self.account["expiry"] = str(expiry)
		return expiry

	def getHeaders(self, accessToken=None, additionalHeader=None, additionalValue=None):
		cookie = self.account.get("drive_stream")
		accessToken = self.account.get("access_token")
		if not accessToken: accessToken = ""
		if not cookie: cookie = ""

		if additionalHeader:
			return {
				"Cookie": "DRIVE_STREAM=" + cookie,
				"Authorization": "Bearer " + accessToken,
				additionalHeader: additionalValue,
			}
		else:
			return {
				"Cookie": "DRIVE_STREAM=" + cookie,
				"Authorization": "Bearer " + accessToken,
			}

	def getHeadersEncoded(self):
		return urllib.parse.urlencode(self.getHeaders())

	def getStreams(self, fileID, resolutionPriority=None):
		url = "https://drive.google.com/get_video_info?docid=" + fileID
		self.account["drive_stream"] = ""
		responseData, cookie = self.sendPayload(url, headers=self.getHeaders(), cookie=True)
		self.account["drive_stream"] = re.findall("DRIVE_STREAM=(.*?);", cookie)[0]

		for _ in range(5):
			responseData = urllib.parse.unquote(responseData)

		# urls = re.sub("\\\\u003d", "=", urls)
		# urls = re.sub("\\\\u0026", "&", urls)
		urls = re.sub("\&url\=https://", "\@", responseData)
		streams = {}
		resolutions = {}

		for r in re.finditer("([\d]+)/[\d]+x([\d]+)", urls, re.DOTALL):
			itag, resolution = r.groups()
			resolution = resolution + "P"
			resolutions[resolution] = itag
			streams[itag] = {"resolution": resolution}

		for r in re.finditer("\@([^\@]+)", urls):
			videoURL = r.group(1)
			itag = re.findall("itag=([\d]+)", videoURL)[0]
			streams[itag]["url"] = "https://" + videoURL + "|" + self.getHeadersEncoded()

		if streams and resolutionPriority:

			for resolution in resolutionPriority:

				if resolution == "Original":
					return
				elif resolution in resolutions:
					return resolution, streams[resolutions[resolution]]["url"]

		elif streams:
			return sorted([(v["resolution"], v["url"]) for k, v in streams.items()], key=lambda x: int(x[0][:-1]), reverse=True)

	def getDrives(self):
		params = {"pageSize": "100"}
		drives = []
		pageToken = True

		while pageToken:
			url = "{}?{}".format(API["drives"], urllib.parse.urlencode(params))
			response = self.sendPayload(url, headers=self.getHeaders())

			pageToken = response.get("nextPageToken")

			if not pageToken:
				drives += response["drives"]
				return drives
			else:
				drives += response["drives"]
				params["pageToken"] = pageToken

	def getDriveID(self):
		url = API["files"] + "/root"
		response = self.sendPayload(url, headers=self.getHeaders())

		if "failed" in response:
			return response

		return response.get("id")

	def downloadFile(self, fileID):
		params = {"alt": "media"}
		url = "{}/{}?{}".format(API["files"], fileID, urllib.parse.urlencode(params))
		return self.sendPayload(url, headers=self.getHeaders(), download=True)

	def getDirectory(self, fileID):
		params = {
			"fields": "parents,name",
			"supportsAllDrives": "true",
			"includeItemsFromAllDrives": "true",
		}
		url = "{}/{}?{}".format(API["files"], fileID, urllib.parse.urlencode(params))
		response = self.sendPayload(url, headers=self.getHeaders())
		return response["name"], response["parents"][0]

	def listDir(self, folderID="root", sharedWithMe=False, foldersOnly=False):

		if foldersOnly:

			if sharedWithMe:
				params = {
					"q": "mimeType='application/vnd.google-apps.folder' and sharedWithMe=true and not trashed",
					"fields": "nextPageToken,files(id,name)",
					"supportsAllDrives": "true",
					"includeItemsFromAllDrives": "true",
					"pageSize": "1000",
				}
			else:
				params = {
					"q": "mimeType='application/vnd.google-apps.folder' and '{}' in parents and not trashed".format(folderID),
					"fields": "nextPageToken,files(id,name)",
					"supportsAllDrives": "true",
					"includeItemsFromAllDrives": "true",
					"pageSize": "1000",
				}

		else:
			params = {
				"q": "'{}' in parents and not trashed".format(folderID),
				"fields": "nextPageToken,files(id,parents,name,mimeType,videoMediaMetadata,fileExtension)",
				"supportsAllDrives": "true",
				"includeItemsFromAllDrives": "true",
				"pageSize": "1000",
			}

		files = []
		pageToken = True

		while pageToken:
			url = "{}?{}".format(API["files"], urllib.parse.urlencode(params))
			response = self.sendPayload(url, headers=self.getHeaders())

			pageToken = response.get("nextPageToken")

			if not pageToken:
				files += response["files"]
				return files
			else:
				files += response["files"]
				params["pageToken"] = pageToken

	def getPageToken(self):
		params = {"supportsAllDrives": "true"}
		url = "{}/startPageToken?{}".format(API["changes"], urllib.parse.urlencode(params))
		response = self.sendPayload(url, headers=self.getHeaders())
		return response.get("startPageToken")

	def getChanges(self, pageToken):
		params = {
			"pageToken": pageToken,
			"fields": "nextPageToken,newStartPageToken,changes(file(id,name,parents,trashed,mimeType,fileExtension,videoMediaMetadata))",
			"supportsAllDrives": "true",
			"includeItemsFromAllDrives": "true",
			"pageSize": "1000",
		}
		changes = {"changes": []}
		nextPageToken = True

		while nextPageToken:
			url = "{}?{}".format(API["changes"], urllib.parse.urlencode(params))
			response = self.sendPayload(url, headers=self.getHeaders())
			nextPageToken = response.get("nextPageToken")

			if not nextPageToken:
				changes["changes"] += response["changes"]
				changes["newStartPageToken"] = response["newStartPageToken"]
				return changes
			else:
				changes["changes"] += response["changes"]
				params["pageToken"] = nextPageToken
