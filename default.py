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

import xbmc

# container = xbmc.getInfoLabel("System.CurrentControlID")
# dbID = xbmc.getInfoLabel("Container(%s).ListItem.DBID" % container)
# dbType = xbmc.getInfoLabel("Container(%s).ListItem.DBTYPE" % container)
# dbType = xbmc.getInfoLabel("Container.ListItem.DBID")
# dbID = xbmc.getInfoLabel("ListItem.FolderPath").split("?")[0].rstrip("/").split("/")[-1]

dbID = xbmc.getInfoLabel("ListItem.DBID")
dbType = xbmc.getInfoLabel("ListItem.DBTYPE")
filePath = xbmc.getInfoLabel("ListItem.FileNameAndPath")

from resources.lib import engine

mediaEngine = engine.ContentEngine()
mediaEngine.run(dbID, dbType, filePath)
