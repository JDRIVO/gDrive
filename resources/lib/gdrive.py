'''
    gdrive XBMC Plugin
    Copyright (C) 2013 dmdsoftware

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


'''

import os
import re
import urllib, urllib2

import xbmc, xbmcaddon, xbmcgui, xbmcplugin

# global variables
addon = xbmcaddon.Addon(id='plugin.video.gdrive')

# helper methods
def log(msg, err=False):
    if err:
        xbmc.log(addon.getAddonInfo('name') + ': ' + msg.encode('utf-8'), xbmc.LOGERROR)    
    else:
        xbmc.log(addon.getAddonInfo('name') + ': ' + msg.encode('utf-8'), xbmc.LOGDEBUG)    


#
# Google Docs API 3 implentation of Google Drive
#
class gdrive:


    API_VERSION = '3.0'
    ##
    # initialize (setting 1) username, 2) password, 3) authorization token, 4) user agent string
    ##
    def __init__(self, user, password, auth, user_agent):
        self.user = user
        self.password = password
        self.writely = auth
        self.user_agent = user_agent

        # if we have an authorization token set, try to use it
        if auth != '':
          log('using token')

          return
        else:
          log('no token - logging in') 
          self.login();
          return


    ##
    # perform login
    ##
    def login(self):

        url = 'https://www.google.com/accounts/ClientLogin'
        header = { 'User-Agent' : self.user_agent }
        values = {
          'Email' : self.user,
          'Passwd' : self.password,
          'accountType' : 'HOSTED_OR_GOOGLE',
          'source' : 'dmdgdrive',
          'service' : 'writely'
        }

        log('logging in') 

        req = urllib2.Request(url, urllib.urlencode(values), header)

        # try login
        try:
            response = urllib2.urlopen(req)
        except urllib2.URLError, e:
            if e.code == 403:
              xbmcgui.Dialog().ok(addon.getLocalizedString(30000), 'Login information is incorrect or permission is denied')
            log(str(e), True)
            return

        response_data = response.read()
        log('response %s' % response_data) 
        log('info %s' % str(response.info())) 

        # retrieve authorization token
        for r in re.finditer('SID=(.*).+?' +
                             'LSID=(.*).+?' +
                             'Auth=(.*).+?' ,
                             response_data, re.DOTALL):
            sid,lsid,auth = r.groups()

        log('parameters: %s %s %s' % (sid, lsid, auth))


        # save authorization token
        self.writely = auth
        return


    ##
    # return the appropriate "headers" for Google Drive requests that include 1) user agent, 2) authorization token, 3) api version
    #   returns: list containing the header
    ##
    def getHeadersList(self):
        return { 'User-Agent' : self.user_agent, 'Authorization' : 'GoogleLogin auth=%s' % self.writely, 'GData-Version' : self.API_VERSION }

    ##
    # return the appropriate "headers" for Google Drive requests that include 1) user agent, 2) authorization token, 3) api version
    #   returns: URL-encoded header string
    ##
    def getHeadersEncoded(self):
        return urllib.urlencode(self.getHeadersList())

    ##
    # retrieve a list of videos, using playback type stream
    #   parameters: prompt for video quality (optional), cache type (optional)
    #   returns: list of videos
    ##
    def getVideosList(self, promptQuality=True, cacheType=0):
        log('getting video list') 

        # retrieve all documents
        url = 'https://docs.google.com/feeds/default/private/full?showfolders=true'

        videos = {}
        while True:
            log('url = %s header = %s' % (url, self.getHeadersList())) 
            req = urllib2.Request(url, None, self.getHeadersList())

            # if action fails, validate login
            log('loading ' + url) 
            try:
              response = urllib2.urlopen(req)
            except urllib2.URLError, e:
              if e.code == 403 or e.code == 401:
                self.login()
                req = urllib2.Request(url, None, self.getHeadersList())
                try:
                  response = urllib2.urlopen(req)
                except urllib2.URLError, e:
                  log(str(e), True)
                  return
              else:
                log(str(e), True)
                return

            response_data = response.read()

            # parsing page for videos
            log('checking video list') 
            # video-entry
            for r in re.finditer('\<entry[^\>]+\>(.*?)\<\/entry\>' ,response_data, re.DOTALL):
                entry = r.group(1)
                log('found entry %s' % (entry))

                # fetch video title, download URL and docid for stream link
                for q in re.finditer('<title>([^<]+)</title><content type=\'video/[^\']+\' src=\'([^\']+)\'.*\;docid=([^\&]+)\&' ,
                             entry, re.DOTALL):

                  title,url,docid = q.groups()
                  log('found video %s %s %s' % (title, url, docid))

                  # memory-cache
                  if cacheType == 0:
                    videos[title] = url

                  # streaming
                  else:
                    if promptQuality:
                      videos[title] = 'plugin://plugin.video.gdrive?mode=streamVideo&promptQuality=true&title=' + title
                    else: 
                      videos[title] = 'plugin://plugin.video.gdrive?mode=streamVideo&title=' + title

            # look for more pages of videos
            nextURL = ''
            for r in re.finditer('<link rel=\'next\' type=\'[^\']+\' href=\'([^\']+)\'' ,
                             response_data, re.DOTALL):
                nextURL = r.groups()
                log('next URL url='+nextURL[0]) 

            response.close()


            # are there more pages to process?
            if nextURL == '':
                break
            else:
                url = nextURL[0]

        log('exit get video') 
        return videos 


    ##
    # retrieve a video link
    #   parameters: title of video
    #   returns: URL of video
    ##
    def getVideoLinkDNU(self,title):
        log('searching for video') 

        # search by video title
	params = urllib.urlencode({'title': title, 'title-exact': 'true'})
        url = 'https://docs.google.com/feeds/default/private/full?' + params
       

        log('url = %s header = %s' % (url, self.getHeadersList())) 
        req = urllib2.Request(url, None, self.getHeadersList())

        # if action fails, validate login
        log('loading ' + url) 
        try:
            response = urllib2.urlopen(req)
        except urllib2.URLError, e:
            if e.code == 403 or e.code == 401:
              self.login()
              req = urllib2.Request(url, None, self.getHeadersList())
              try:
                response = urllib2.urlopen(req)
              except urllib2.URLError, e:
                log(str(e), True)
                return
            else:
              log(str(e), True)
              return

        response_data = response.read()


        # fetch video title, download URL and docid for stream link
        log('checking search result') 
        for r in re.finditer('<title>([^<]+)</title><content type=\'video/[^\']+\' src=\'([^\']+)\'' ,
                             response_data, re.DOTALL):
          title,url = r.groups()
          log('found video %s %s' % (title, url)) 
          videoURL = url

        response.close()

 
        log('exit get video') 
        return videoURL 


    ##
    # retrieve a video link
    #   parameters: title of video, whether to prompt for quality/format (optional), cache type (optional)
    #   returns: list of URLs for the video or single URL of video (if not prompting for quality)
    ##
    def getVideoLink(self,title,promptQuality=False,cacheType=0):
        log('searching for video') 


        # search by video title
	params = urllib.urlencode({'title': title, 'title-exact': 'true'})
        url = 'https://docs.google.com/feeds/default/private/full?' + params
       

        log('url = %s header = %s' % (url, self.getHeadersList())) 
        req = urllib2.Request(url, None, self.getHeadersList())


        # if action fails, validate login
        log('loading ' + url) 
        try:
            response = urllib2.urlopen(req)
        except urllib2.URLError, e:
            if e.code == 403 or e.code == 401:
              self.login()
              req = urllib2.Request(url, None, self.getHeadersList())
              try:
                response = urllib2.urlopen(req)
              except urllib2.URLError, e:
                log(str(e), True)
                return
            else:
              log(str(e), True)
              return

        response_data = response.read()


        # fetch video title, download URL and docid for stream link
        log('checking search result') 
        for r in re.finditer('\<entry[^\>]+\>(.*?)\<\/entry\>' ,response_data, re.DOTALL):
             entry = r.group(1)
             log('found entry %s' % (entry))
             for q in re.finditer('<title>([^<]+)</title><content type=\'video/[^\']+\' src=\'([^\']+)\'.*\;docid=([^\&]+)\&' ,
                             entry, re.DOTALL):
               title,url,docid = q.groups()
               log('found video %s %s %s' % (title, url, docid))


        response.close()
        log('exit get video') 

        if cacheType == 0:
          return url
        else:
          # if we are instructed to prompt for quality, we will return a list of playback links, otherwise, return a single playback link
          if promptQuality == True:
            return self.getVideoStream(docid, True)
          else:
            return self.getVideoStream(docid)

 

    ##
    # retrieve a stream link
    #   parameters: docid of video, whether to prompt for quality/format (optional)
    #   returns: list of streams for the video or single stream of video (if not prompting for quality)
    ## 
    def getVideoStream(self,docid,promptQuality=False):
        log('fetching player link') 


        # player using docid
	params = urllib.urlencode({'docid': docid})
        url = 'https://docs.google.com/get_video_info?docid=' + str((docid))
       

        log('url = %s header = %s' % (url, self.getHeadersList())) 
        req = urllib2.Request(url, None, self.getHeadersList())


        # if action fails, validate login
        log('loading ' + url) 
        try:
            response = urllib2.urlopen(req)
        except urllib2.URLError, e:
            if e.code == 403 or e.code == 401:
              self.login()
              req = urllib2.Request(url, None, self.getHeadersList())
              try:
                response = urllib2.urlopen(req)
              except urllib2.URLError, e:
                log(str(e), True)
                return
            else:
              log(str(e), True)
              return

        response_data = response.read()


        log('response %s' % response_data) 
        log('info %s' % str(response.info())) 
        log('checking search result')


        # decode resulting player URL (URL is composed of many sub-URLs)
        urls = response_data
        urls = urllib.unquote(urllib.unquote(urllib.unquote(urllib.unquote(urllib.unquote(urls)))))

        # do some substitutions to make anchoring the URL easier
        log('urls --- %s ' % urls) 
        urls = re.sub('\&url\=https://', '\@', urls)
        log('found urlsss %s' % urls) 


        # fetch format type and quality for each stream
        videos = {}
        for r in re.finditer('\@([^\@]+)' ,urls):
          videoURL = r.group(1)
          for q in re.finditer('type\=video\/([^\&]+)\&quality\=(\w+)' ,
                             videoURL, re.DOTALL):
            (videoType,quality) = q.groups()
            videos[videoType + ' - ' + quality] = 'https://' + videoURL
            log('found videoURL %s' % (videoURL)) 

        response.close()

        log('exit get video select %s' %(videos)) 
        # if we are instructed to prompt for quality, we will return a list of playback links, otherwise, return a single playback link
        if promptQuality == True:
          return videos
        else:
          return 'https://' + videoURL

