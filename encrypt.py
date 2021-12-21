import os
import sys

import encryption

saltFile = sys.argv[1]
password = sys.argv[2]
filePath = sys.argv[3]
destinationPath = sys.argv[4]

encrypt = encryption.Encryption(saltFile, password)

filename = os.path.basename(filePath)
encryptedFilename = encrypt.encryptString(filename)
print(encryptedFilename)

destinationPath = os.path.join(destinationPath, encryptedFilename.decode("utf-8"))
encrypt.encryptFile(filePath, destinationPath)
