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
