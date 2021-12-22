# To be ran by the script that uploads files to Google Drive. Sync strms with resilio, syncthing etc. Install watchdog on Kodi.

import sys
import json
import shlex
import subprocess

videoPath = sys.argv[1]
encryptedFilePath = sys.argv[2]
strmPath = sys.argv[3]

# videoPath = "/home/jack/movies/best movie 2000.mkv"
# encryptedFilePath = "remote:/folder/RrtgFuvcxsWfKuFgGJ34VvcgfGFGWEWet"
# strmPath = "/home/jack/strm/movies/best movie 2000.strm"

cmd = "ffprobe -v quiet -print_format json -show_format -show_streams"
args = shlex.split(cmd)
args.append(videoPath)
ffprobeOutput = subprocess.check_output(args).decode("utf-8")
ffprobeOutput = json.loads(ffprobeOutput)

mediaInfo = {}
mediaInfo["video_duration"] = ffprobeOutput["format"]["duration"]
video = audio = False

for dic in ffprobeOutput["streams"]:
	codecType = dic.get("codec_type")

	if codecType == "video" and not video:
		video = True
		videoCodec = dic.get("codec_name")
		videoWidth = dic.get("width")
		videoHeight = dic.get("height")
		colourTransfer = dic.get("color_transfer")

		if videoCodec:
			mediaInfo["video_codec"] = videoCodec

		if videoWidth:
			mediaInfo["video_width"] = videoWidth

		if videoHeight:
			mediaInfo["video_height"] = videoHeight

		if videoWidth and videoHeight:
			mediaInfo["aspect_ratio"] = videoWidth / videoHeight

		if colourTransfer in ("smpte2084", "smpte2086"):
			mediaInfo["hdr"] = "hdr10"
		elif colourTransfer == "arib-std-b67":
			mediaInfo["hdr"] = "hlg"
		elif dic.get("codec_tag_string") == "dvhe":
			mediaInfo["hdr"] = "dolbyvision"

	elif codecType == "audio" and not audio:
		audio = True
		audioCodec = dic.get("codec_name")
		audioChannels = dic.get("channels")

		if audioCodec:
			mediaInfo["audio_codec"] = audioCodec

		if audioChannels:
			mediaInfo["audio_channels"] = audioChannels

cmd = "rclone lsf --format i"
args = shlex.split(cmd)
args.append(encryptedFilePath)
fileID = subprocess.check_output(args).strip().decode("utf-8")
mediaInfo["filename"] = fileID

with open(strmPath, "w+") as strm:
	# Every paramater is optional besides the filename (Google Drive File ID) - essential strm format is:
	# plugin://plugin.video.gdrive/?mode=video&encfs=True&filename=7ctPNMUl4m8B4KBwY
	url = "plugin://plugin.video.gdrive/?mode=video&encfs=True" + "".join(["&{}={}".format(k, v) for k, v in mediaInfo.items()])
	strm.write(url)
