import os
import shutil

FS_PROHIBITED_CHARS = (
	"<",
	">",
	"/",
	"\\",
	"?",
	"*",
	":",
	"|",
	'"',
)

SUBTITLES = (
	"srt",
	"ssa",
	"vtt",
	"sub",
	"ttml",
	"sami",
	"ass",
	"idx",
	"sbv",
	"stl",
	"smi",
)

VIDEO_FILE_EXTENSIONS = (
	"mpg",
	"mp2",
	"mpeg",
	"mpe",
	"mpv",
	"avi",
	"mov",
	"mkv",
)


class FileOperations:

	def downloadFiles(self, files, dirPath, cachedFiles, folderID, fileIDs):

		for file in list(files):
			fileID = file["id"]
			filename = file["filename"]
			encrypted = file["encrypted"]
			filePath = self.generateFilePath(dirPath, self.removeProhibitedFSchars(filename))

			if encrypted:
				self.downloadEncryptedFile(dirPath, filePath, fileID)
			else:
				self.downloadFile(dirPath, filePath, fileID)

			cachedFiles[fileID] = [
				filename,
				filename,
				folderID,
				"rename&delete",
				"original"
			]

			if fileID not in fileIDs:
				fileIDs.append(fileID)

			files.remove(file)

	def downloadFile(self, dirPath, filePath, fileID):
		self.createDirs(dirPath)
		file = self.cloudService.downloadFile(fileID)

		with open(filePath, "wb") as f:
			f.write(file.read())

	def downloadEncryptedFile(self, dirPath, filePath, fileID):
		self.createDirs(dirPath)
		encryptedFile = self.cloudService.downloadFile(fileID)
		self.encryption.decryptStream(encryptedFile, filePath)

	def decryptFilename(self, filename):
		decryptedFilename = self.encryption.decryptString(filename)

		if decryptedFilename:
			return decryptedFilename.decode("utf-8")

	@staticmethod
	def identifyFile(filename, fileExtension, mimeType):

		if mimeType == "application/vnd.google-apps.folder":
			return "folder"

		if not fileExtension:
			return

		fileExtension = fileExtension.lower()

		if "video" in mimeType or fileExtension in VIDEO_FILE_EXTENSIONS:
			return "video"
		elif fileExtension == "nfo":
			return "nfo"
		elif fileExtension == "jpg":
			fileNameLowerCase = filename.lower()

			if "poster" in fileNameLowerCase:
				return "poster"
			elif "fanart" in fileNameLowerCase:
				return "fanart"

		elif fileExtension in SUBTITLES:
			return "subtitles"
		elif fileExtension == "strm":
			return "strm"

	def deleteFiles(self, strmRoot, folderID, cachedDirectories, cachedFiles):

		if not cachedDirectories.get(folderID):
			return

		cachedDirPath, cachedRootFolderID, cachedParentFolderID, folderIDs, fileIDs = cachedDirectories[folderID]

		for fileID in fileIDs:
			cachedFile, cachedOriginalFilename, cachedParentFolderID, mode, folderStructure = cachedFiles[fileID]

			if folderStructure == "original":
				self.deleteFile(strmRoot, dirPath=cachedDirPath, filename=cachedFile)
			else:
				self.deleteFile(strmRoot, filePath=cachedFile)

			del cachedFiles[fileID]

		for dirID in folderIDs:
			self.deleteFiles(strmRoot, dirID, cachedDirectories, cachedFiles)

		del cachedDirectories[folderID]

	def deleteFile(self, strmRoot, filePath=None, dirPath=None, filename=None):

		if not filePath:
			filePath = os.path.join(dirPath, filename)
		else:
			dirPath, filename = os.path.split(filePath)

		if os.path.exists(filePath):
			os.remove(filePath)

		self.deleteEmptyDirs(dirPath, strmRoot)

	@staticmethod
	def createDirs(dirPath):

		if not os.path.exists(dirPath):
			os.makedirs(dirPath)

	def renameFile(self, strmRoot, oldPath, dirPath, newName):
		self.createDirs(dirPath)
		newPath = self.duplicateFileCheck(dirPath, newName)
		shutil.move(oldPath, newPath)
		self.deleteEmptyDirs(os.path.dirname(oldPath), strmRoot)
		return newPath

	def renameFolder(self, strmRoot, oldPath, newPath):

		if os.path.exists(oldPath):
			shutil.move(oldPath, newPath)
			self.deleteEmptyDirs(os.path.dirname(oldPath), strmRoot)

	@staticmethod
	def deleteEmptyDirs(dirPath, strmRoot):

		while dirPath != strmRoot and os.path.exists(dirPath) and not os.listdir(dirPath):
			os.rmdir(dirPath)
			dirPath = dirPath.rsplit(os.sep, 1)[0]

	def generateFilePath(self, dirPath, filename):
		return self.duplicateFileCheck(dirPath, filename)

	@staticmethod
	def duplicateFileCheck(dirPath, filename):
		filePath = os.path.join(dirPath, filename)
		filename, fileExtension = os.path.splitext(filename)
		copy = 1

		while os.path.exists(filePath):
			filePath = os.path.join(dirPath, "{} ({}){}".format(filename, copy, fileExtension))
			copy += 1

		return filePath

	def createStrm(self, dirPath, strmPath, contents, encrypted):
		self.createDirs(dirPath)

		with open (strmPath, "w+") as strm:
			url = "plugin://plugin.video.gdrive/?mode=video&encfs=" + str(encrypted) + "".join(["&{}={}".format(k, v) for k, v in contents.items() if v])
			strm.write(url)

	@staticmethod
	def removeProhibitedFSchars(name):
		return "".join([chr for chr in name if chr not in FS_PROHIBITED_CHARS])
