import os
import sys
import encryption

saltFile = sys.argv[1]
password = sys.argv[2]
filePath = sys.argv[3]
destinationPath = sys.argv[4]

decrypt = encryption.Encryption(saltFile, password)

encryptedFilename = os.path.basename(filePath)
filename = decrypt.decryptString(encryptedFilename)

destinationPath = os.path.join(destinationPath, filename.decode("utf-8"))
decrypt.decryptFile(filePath, destinationPath)
