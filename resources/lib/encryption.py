# http://stackoverflow.com/questions/6425131/encrpyt-decrypt-data-in-python-with-salt

import os
import base64
import random
import struct
import string
import hashlib

try:
	import Cryptodome.Random
	from Cryptodome.Cipher import AES
except:
	import Crypto.Random
	from Crypto.Cipher import AES


class Encryption:
	# salt size in bytes
	SALT_SIZE = 32
	# number of iterations in the key generation
	NUMBER_OF_ITERATIONS = 20
	# the size multiple required for AES
	AES_MULTIPLE = 16

	def __init__(self, saltFile, saltPassword):

		try:

			with open(saltFile, "rb") as salt:
				self.salt = salt.read()

		except:

			with open(saltFile, "wb") as salt:
				self.salt = self.generateSalt()
				salt.write(self.salt)

		if saltPassword:
			self.key = self.generateKey(saltPassword)

	def generateKey(self, password, iterations=NUMBER_OF_ITERATIONS):

		if not iterations > 0:
			return

		key = password.encode("utf-8") + self.salt

		for i in range(iterations):
			key = hashlib.sha256(key).digest()

		return key

	def generateSalt(self, size=SALT_SIZE):
		return "".join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(size)).encode("utf-8")

	def padText(text, multiple):
		extraBytes = len(text) % multiple
		paddingSize = multiple - extraBytes
		padding = chr(paddingSize) * paddingSize
		paddedText = text + padding
		return paddedText

	def unpadText(paddedText):
		paddingSize = ord(paddedText[-1])
		text = paddedText[:-paddingSize]
		return text

	def encryptFilename(fileName):
		return base64.b64encode(fileName)

	def decrypt(fileName):

		try:
			return base64.b64decode(fileName)
		except:
			return ""

	def decryptFile(self, inFilename, outFilename=None, chunkSize=24 * 1024):
		""" Decrypts a file using AES (CBC mode) with the
			given key. Parameters are similar to encryptFile,
			with one difference: outFilename, if not supplied
			will be inFilename without its last extension
			(i.e. if inFilename is 'aaa.zip.enc' then
			outFilename will be 'aaa.zip')
		"""

		if not outFilename:
			outFilename = os.path.splitext(inFilename)[0]

		with open(inFilename, "rb") as inFile:
			origSize = struct.unpack("<Q", inFile.read(struct.calcsize("Q")))[0]
			# iv = inFile.read(16)
			# decryptor = AES.new(key, AES.MODE_CBC, iv)
			# key = generateKey(password, salt, NUMBER_OF_ITERATIONS)
			decryptor = AES.new(self.key, AES.MODE_ECB)

			with open(outFilename, "wb") as outFile:

				while True:
					chunk = inFile.read(chunkSize)

					if len(chunk) == 0:
						break

					outFile.write(decryptor.decrypt(chunk))

				outFile.truncate(origSize)

	def decryptStream(self, response, chunkSize=24 * 1024):
		# with open(inFilename, "rb") as inFile:
			origSize = struct.unpack("<Q", response.read(struct.calcsize("Q")))[0]
			decryptor = AES.new(self.key, AES.MODE_ECB)

			with open(outFilename, "w") as outFile:

				while True:
					chunk = response.read(chunkSize)

					if len(chunk) == 0:
						break

					outFile.write(decryptor.decrypt(chunk))

				outFile.truncate(origSize)

	def decryptStreamChunkOld(self, response, wfile, chunkSize=24 * 1024, startOffset=0):
		# with open(inFilename, "rb") as inFile:
			origSize = struct.unpack("<Q", response.read(struct.calcsize("Q")))[0]
			decryptor = AES.new(self.key, AES.MODE_ECB)
			count = 0

			while True:
				chunk = response.read(chunkSize)
				count += 1

				if len(chunk) == 0:
					break

				responseChunk = decryptor.decrypt(chunk)

				if count == 1 and startOffset != 0:
					wfile.write(responseChunk[startOffset:])
				elif len(chunk) < len(responseChunk.strip()):
					wfile.write(responseChunk.strip())
				else:
					wfile.write(responseChunk)

	def decryptStreamChunk(self, response, wfile, adjStart=0, adjEnd=0, chunkSize=16 * 1024):
		# origSize = struct.unpack("<Q", response.read(struct.calcsize("Q")))[0]
		decryptor = AES.new(self.key, AES.MODE_ECB)
		responseChunk = ""
		count = sending = 0

		# firstChunkSize = chunkSize + adjStart
		# if adjStart > 0:
			# firstChunk = response.read(adjStart)
			# adjStart = 0

		chunk = response.read(chunkSize)

		while True:
			nextChunk = response.read(chunkSize)
			count += 1

			if len(chunk) == 0:
				break

			responseChunk = decryptor.decrypt(chunk)

			if count == 1 and adjStart > 0 and len(nextChunk) == 0:
				wfile.write(responseChunk[adjStart:].strip())
				adjStart = 0
			elif count == 1 and adjStart > 0:
				wfile.write(responseChunk[adjStart:])
				adjStart = 0
			elif len(nextChunk) == 0 and adjEnd > 0:
				wfile.write(responseChunk[:len(responseChunk) - adjEnd])
				adjEnd = 0
			elif len(nextChunk) == 0:  # adjEnd = 0
				wfile.write(responseChunk.strip())
			else:
				wfile.write(responseChunk)

			chunk = nextChunk

	def decryptCalculatePadding(self, response, chunkSize=24 * 1024):
		# with open(inFilename, "rb") as inFile:
			origSize = struct.unpack("<Q", response.read(struct.calcsize("Q")))[0]
			decryptor = AES.new(self.key, AES.MODE_ECB)
			count = 0

			while True:
				chunk = response.read(chunkSize)
				count += 1

				if len(chunk) == 0:
					break

				responseChunk = decryptor.decrypt(chunk)
				return int(len(chunk) - len(responseChunk.strip()))

	def decryptCalculateSizing(self, response):
		# with open(inFilename, "rb") as inFile:
			origSize = struct.unpack("<Q", response.read(struct.calcsize("Q")))[0]
			decryptor = AES.new(self.key, AES.MODE_ECB)
			return origSize

	def decryptStreamChunk2(self, response, wfile, chunkSize=24 * 1024, startOffset=0):
		# with open(inFilename, "rb") as inFile:
			origSize = struct.unpack("<Q", response.read(struct.calcsize("Q")))[0]
			decryptor = AES.new(self.key, AES.MODE_ECB)

			while True:
				chunk = response.read(chunkSize)

				if len(chunk) == 0:
					break

				wfile.write(decryptor.decrypt(chunk))

	def encryptFile(self, inFilename, outFilename=None, chunkSize=64 * 1024):
		""" Encrypts a file using AES (CBC mode) with the
			given key.

			key:
				The encryption key - a string that must be
				either 16, 24 or 32 bytes long. Longer keys
				are more secure.

			inFilename:
				Name of the input file

			outFilename:
				If None, '<inFilename>.enc' will be used.

			chunkSize:
				Sets the size of the chunk which the function
				uses to read and encrypt the file. Larger chunk
				sizes can be faster for some files and machines.
				chunksize must be divisible by 16.
		"""

		if not outFilename:
			outFilename = inFilename + ".enc"

		# key = generateKey(key, salt, NUMBER_OF_ITERATIONS)
		# iv = "".join(chr(random.randint(0, 0xFF)) for i in range(16))
		encryptor = AES.new(self.key, AES.MODE_ECB)
		fileSize = os.path.getsize(inFilename)

		with open(inFilename, "rb") as inFile:

			with open(outFilename, "wb") as outFile:
				outFile.write(struct.pack("<Q", fileSize))
				# outFile.write(iv)

				while True:
					chunk = inFile.read(chunkSize)

					if len(chunk) == 0:
						break
					elif len(chunk) % 16 != 0:
						chunk += b" " * (16 - len(chunk) % 16)

					outFile.write(encryptor.encrypt(chunk))

	def encryptString(self, stringDecrypted):
		# key = generateKey(key, salt, NUMBER_OF_ITERATIONS)
		# iv = "".join(chr(random.randint(0, 0xFF)) for i in range(16))
		encryptor = AES.new(self.key, AES.MODE_ECB)

		if len(stringDecrypted) == 0:
			return
		elif len(stringDecrypted) % 16 != 0:
			stringDecrypted += " " * (16 - len(stringDecrypted) % 16)

		return base64.b64encode(encryptor.encrypt(stringDecrypted.encode("utf-8"))).replace(b"/", b"---")

	def decryptString(self, stringEncrypted):
		decryptor = AES.new(self.key, AES.MODE_ECB)

		if len(stringEncrypted) == 0:
			return

		return decryptor.decrypt(base64.b64decode(stringEncrypted.replace("---", "/").encode("utf-8"))).rstrip()
