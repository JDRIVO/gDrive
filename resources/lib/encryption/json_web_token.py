import json
import time
import base64

try:
	from Cryptodome.Hash import SHA256
	from Cryptodome.PublicKey import RSA
	from Cryptodome.Signature import pkcs1_15
except Exception:
	from Crypto.Hash import SHA256
	from Crypto.PublicKey import RSA
	from Crypto.Signature import pkcs1_15


class JsonWebToken:

	def __init__(self, email, key, scope, authURL):
		self.key = key
		self.headers = {
			"alg": "RS256",
			"typ": "JWT",
		}
		iat = time.time()
		exp = iat + 3600
		self.claimSet = {
			"iss": email,
			"scope": scope,
			"aud": authURL,
			"exp": exp,
			"iat": iat,
		}

	@staticmethod
	def encode(input):
		return base64.urlsafe_b64encode(input).decode("utf-8").rstrip("=")

	def create(self):
		key = self.key.encode("utf-8")
		claimSet = json.dumps(self.claimSet).encode("utf-8")
		headers = json.dumps(self.headers).encode("utf-8")

		segments = []
		segments.append(self.encode(headers))
		segments.append(self.encode(claimSet))
		sigContent = ".".join(segments).encode("utf-8")

		key = RSA.import_key(key)
		h = SHA256.new(sigContent)
		signature = pkcs1_15.new(key).sign(h)
		segments.append(self.encode(signature))
		return ".".join(segments)
