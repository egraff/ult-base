import os
import subprocess

def __unpackAppListToWhichCommand(appList):
  if isinstance(appList, basestring):
    appList = [appList]

  return "||".join("which %s" % (app,) for app in appList)


def __locateTestUtility(appName, appCmds):
  whichCommand = __unpackAppListToWhichCommand(appCmds)
  whichApp = subprocess.Popen(["sh", "-c", whichCommand], env=os.environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  stdout, stderr = whichApp.communicate()
  whichApp.wait()

  app = stdout.strip()

  if not len(app):
    raise Exception("The test utility %s could not be found in the system! Have you installed it?" % (appName,))

  return os.path.basename(app)


def getPDFInfo():
  return __locateTestUtility("PDFInfo", "pdfinfo")


def getGhostScript():
  return __locateTestUtility("GhostScript", ["gs", "gswin64c", "gswin32c"])


def getCompare():
  return __locateTestUtility("Compare (ImageMagick)", "compare")
