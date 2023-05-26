# To be ran by the script that uploads files to Google Drive. Sync strms with resilio, syncthing etc. Install watchdog on Kodi.

import os
import re
import sys
import json
import shlex
import subprocess

videoPath = sys.argv[1]
remoteVideoPath = sys.argv[2]
strmPath = sys.argv[3]
driveID = sys.argv[4] # Optional - if not included you will need to manually set the playback account in settings

# videoPath = "/home/jack/movies/best movie 2000.mkv"
# remoteVideoPath = "remote:/folder/RrtgFuvcxsWfKuFgGJ34VvcgfGFGWEWet"
# strmPath = "/home/jack/strm/movies/best movie 2000.strm"
# driveID = "0AGHbAfUtSfVATg4F5B"

cmd = "ffprobe -v quiet -print_format json -show_format -show_streams"
args = shlex.split(cmd)
args.append(videoPath)
ffprobeOutput = subprocess.check_output(args).decode("utf-8")
ffprobeOutput = json.loads(ffprobeOutput)

strmInfo = {}
strmInfo["video_duration"] = ffprobeOutput["format"]["duration"]
video = audio = False

for dic in ffprobeOutput["streams"]:
	codecType = dic.get("codec_type")

	if codecType == "video":

		if strmInfo.get("hdr") == "dolbyvision":
			continue

		codecTag = dic.get("codec_tag_string")
		colourTransfer = dic.get("color_transfer")
		sideData = dic.get("side_data_list")

		if codecTag in ("dva1", "dvav", "dvh1", "dvhe"):
			strmInfo["hdr"] = "dolbyvision"
			codecs = {"dva1": "h264", "dvav": "h264", "dvh1": "hevc", "dvhe": "hevc"}
			strmInfo["video_codec"] = codecs[codecTag]
		elif sideData and "dv_profile" in str(sideData):
			strmInfo["hdr"] = "dolbyvision"
		elif colourTransfer in ("smpte2084", "smpte2086", "smpte2094"):
			strmInfo["hdr"] = "hdr10"
		elif colourTransfer == "arib-std-b67":
			strmInfo["hdr"] = "hlg"

		if video:
			continue

		video = True
		videoCodec = dic.get("codec_name")
		videoWidth = dic.get("width")
		videoHeight = dic.get("height")

		if videoCodec and not strmInfo.get("video_codec"):
			strmInfo["video_codec"] = videoCodec

		if videoWidth:
			strmInfo["video_width"] = videoWidth

		if videoHeight:
			strmInfo["video_height"] = videoHeight

		if videoWidth and videoHeight:
			strmInfo["aspect_ratio"] = videoWidth / videoHeight

	elif codecType == "audio" and not audio:
		audio = True
		audioCodec = dic.get("codec_name")
		audioChannels = dic.get("channels")

		if audioCodec:
			strmInfo["audio_codec"] = audioCodec

		if audioChannels:
			strmInfo["audio_channels"] = audioChannels

filename = os.path.basename(videoPath)

if re.search("[-_. ](dv|dovi|dolby[-_. ]*vision)[-_. ]", filename, re.IGNORECASE):
	strmInfo["hdr"] = "dolbyvision"
elif not strmInfo.get("hdr") and re.search("hdr10", filename, re.IGNORECASE):
	strmInfo["hdr"] = "hdr10"

cmd = "rclone lsf --format i"
args = shlex.split(cmd)
args.append(remoteVideoPath)
fileID = subprocess.check_output(args).strip().decode("utf-8")
strmInfo["file_id"] = fileID

if driveID:
	strmInfo["drive_id"] = driveID

with open(strmPath, "w+") as strm:

	# Essential strm format for unencrypted videos:
	# plugin://plugin.video.gdrive/?mode=video&encrypted=False&file_id=7ctPNMUl4m8B4KBwY

	# Essential strm format for gDrive encrypted videos:
	# plugin://plugin.video.gdrive/?mode=video&encrypted=True&file_id=7ctPNMUl4m8B4KBwY

	url = "plugin://plugin.video.gdrive/?mode=video&encrypted=True" + "".join(["&{}={}".format(k, v) for k, v in strmInfo.items()])
	strm.write(url)
