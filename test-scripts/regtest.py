#!/usr/bin/env python

import os
import re
import sys
import json
import traceback
import threading
import subprocess

import asynclib
from testutil import ComparePngsAsyncTask, PdfFile, mkdirp


class debug:
  NORMAL = "\\033[0m"
  INFO  = "\\033[1;34m"
  DEBUG = "\\033[0;32m"
  WARNING = "\\033[1;33m"
  YELLOW = "\\033[1;33m"
  BLUE = "\\033[1;34m"
  ERROR = "\\033[1;31m"
  FUCK = "\\033[1;41m"
  GREEN = "\\033[1;32m"
  WHITE = "\\033[1;37m"
  BOLD = "\\033[1m"
  UNDERLINE = "\\033[4m"

dlvl = [
  debug.INFO,
  debug.DEBUG,
  debug.WARNING,
  debug.FUCK,
  debug.NORMAL,
  debug.BOLD,
  debug.UNDERLINE,
  debug.WHITE,
  debug.GREEN,
  debug.YELLOW,
  debug.BLUE,
  debug.ERROR
]


class TestPdfPagePair(asynclib.AsyncTask):
  def __init__(self, config, testPdfObj, protoPdfObj, pageNum, testName):
    self.config = config
    self.pageNum = pageNum

    tmpTestsDir = "%s/tests" % (config.TMPDIR,)
    tmpProtoDir = "%s/proto" % (config.TMPDIR,)
    diffDir = config.DIFFDIR

    self.testPngPagePath = "%s/%s_%s.png" % (tmpTestsDir, testName, self.pageNum)
    self.protoPngPagePath = "%s/%s_%s.png" % (tmpProtoDir, testName, self.pageNum)
    self.diffPath = "%s/%s_%s.png" % (diffDir, testName, self.pageNum)

    mkdirp(os.path.dirname(self.testPngPagePath))
    mkdirp(os.path.dirname(self.protoPngPagePath))
    mkdirp(os.path.dirname(self.diffPath))

    # Start processes for generating PNGs
    config.processPoolSemaphore.acquire()
    self.testPdfTask = testPdfObj.getPngForPageAsync(pageNum, self.testPngPagePath)
    self.protoPdfTask = protoPdfObj.getPngForPageAsync(pageNum, self.protoPngPagePath)

    # Wait asynchronously for PNG processes to complete
    # Note: we start a worker thread with await(), because we want to initiate the
    # compare operation as soon as possible, rather than after self.wait() has been
    # called.
    self.joinedPdfTask = asynclib.JoinedAsyncTask(self.testPdfTask, self.protoPdfTask)
    self.joinedPdfTask.await(self._compare)

    # Wait routine for this task is thread-join for joined task
    self.wait = self.joinedPdfTask.wait

  def _compare(self, results):
    genPngProcResults = results

    genTestPngProcResults, genProtoPngProcResults = genPngProcResults
    genTestPngProc, _stdout, _stderr = genTestPngProcResults
    genProtoPngProc, _stdout, _stderr = genProtoPngProcResults

    assert genTestPngProc.returncode == 0, "Failed to generate PNG %s" % (self.testPngPagePath,)
    assert genProtoPngProc.returncode == 0, "Failed to generate PNG %s" % (self.protoPngPagePath,)

    task = ComparePngsAsyncTask(self.testPngPagePath, self.protoPngPagePath, self.diffPath)

    # Wait synchronously since we're already executing in separate thread
    try:
      task.wait()
    finally:
      self.config.processPoolSemaphore.release()

    aeDiff = task.result

    self.__pngsAreEqual = (aeDiff == 0)

    if self.__pngsAreEqual:
      os.remove(self.testPngPagePath)
      os.remove(self.protoPngPagePath)
      try:
        os.remove(self.diffPath)
      except OSError:
        pass

    self.__result = (self.pageNum, self.__pngsAreEqual)

  # Result is on the form (pagenum, PNGs are equal)
  @property
  def result(self):
    return self.__result


# Use file name of PDF to determine which pages we want to test
def determineListOfPagesToTest(pdfObj):
  numPages = pdfObj.numPhysicalPages()
  basename = os.path.basename(pdfObj.path)
  noext = os.path.splitext(basename)[0]

  # search for a range in filename ( denoted with [ ] ) and save only the range
  textrange = re.search(r"\[.*\]", noext)
  if textrange is not None:
    # remove brackets and commas
    textrange = re.sub(r"([\[\]])", r"", textrange.group()).replace(r",", " ")
    pageList = []

    # make list and translate hyphen into a sequence, e.g 3-6 -> "3 4 5 6"
    for num in textrange.split(" "):
      if "-" in num:
        numrange = num.split("-")
        assert len(numrange) == 2

        numrange = range(int(numrange[0]), int(numrange[1]) + 1)
        pageList.extend(numrange)
      else:
        pageList.append(int(num))

    pageList = sorted(set(pageList))

    for pageNum in pageList:
      assert pageNum <= numPages
  else:
    pageList = range(1, numPages + 1)

  return pageList


class TestPdfPair(asynclib.AsyncTask):
  def __init__(self, config, testName):
    self.testName = testName

    testPdfPath = "%s/%s.pdf" % (config.PDFSDIR, testName)
    protoPdfPath = "%s/%s.pdf" % (config.PROTODIR, testName)

    config.processPoolSemaphore.acquire()
    try:
      testPdfObj = PdfFile(testPdfPath)
      protoPdfObj = PdfFile(protoPdfPath)
    finally:
      config.processPoolSemaphore.release()

    testPageList = determineListOfPagesToTest(testPdfObj)
    protoPageList = determineListOfPagesToTest(protoPdfObj)

    pageList = set(testPageList + protoPageList)

    self.failedPages = []

    testTasks = []
    for pageNum in pageList:
      if pageNum not in testPageList or pageNum not in protoPageList:
        self.failedPages.append(pageNum)
        continue

      task = TestPdfPagePair(config, testPdfObj, protoPdfObj, pageNum, testName)
      testTasks.append(task)

    self.__joinedTestTask = asynclib.JoinedAsyncTask(*testTasks)
    self.wait = self.__joinedTestTask.wait

  # Result is on the form (testname, list of failed pages)
  @property
  def result(self):
    pngResults = self.__joinedTestTask.result

    for pageNum, pngsAreEqual in pngResults:
      if not pngsAreEqual:
        self.failedPages.append(pageNum)

    return (self.testName, self.failedPages)


def makeTestTask(config, testName):
  cmd = ['make', '-C', config.TESTDIR, '--no-print-directory', '_file', 'RETAINBUILDFLD=y', 'FILE=%s.tex' % (testName,)]
  task = asynclib.AsyncPopen(cmd, shell=False, env=os.environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  return task


class TestTask(asynclib.AsyncTask):
  def __init__(self, config, testName):
    self.config = config
    self.testName = testName

    config.makeTaskSemaphore.acquire()
    task = makeTestTask(config, self.testName)
    task.await(self._makeTaskComplete)
    self.wait = task.wait

  def _makeTaskComplete(self, procResults):
    self.config.makeTaskSemaphore.release()

    proc, stdout, stderr = procResults

    if proc.returncode != 0:
      self.__result = (self.testName, False, None, (proc, stdout, stderr))
      return

    try:
      task = TestPdfPair(self.config, self.testName)
    except:
      self.__result = (self.testName, True, sys.exc_info(), None)
      return
    else:
      task.wait()
      _, failedPages = task.result

      self.__result = (self.testName, True, None, failedPages)

  # Result is on the form
  #  (test name, build succeeded = TRUE, exception = None, list of failed pages)
  # or
  #  (test name, build succeeded = TRUE, exc_info, None)
  # or
  #  (test name, build succeeded = FALSE, None, (build proc, stdout, stderr))
  @property
  def result(self):
    return self.__result


class TestRunner():
  def __init__(self, config):
    self.testResultLock = threading.Lock()
    self.numTestsCompleted = 0
    self.failedTests = []
    self.tasks = []
    self.config = config

  def echo(self, *string):
    color = ""
    if string[0] in dlvl:
      if dlvl.index(string[0]) < dlvl.index(self.config.DEBUGLEVEL):
        return

      color = string[0]
      string = string[1:]

    echoStr = ' '.join(str(x) for x in string)
    with self.config.echoLock:
      subprocess.Popen([
        'sh',
        '-c',
        'printf "%s"; printf %r; printf "%s"' % (color, echoStr, '\\033[0m')
      ]).wait()

  def __testCallback(self, result):
    testName, buildSucceeded, exception, failedPages = result
    testPassed = buildSucceeded and (exception is None) and (len(failedPages) == 0)

    with self.testResultLock:
      if self.numTestsCompleted % self.config.NUM_DOTS_PER_LINE == 0:
        self.echo(debug.BOLD, "\n")

      self.numTestsCompleted += 1

      if testPassed:
        self.echo(debug.GREEN, ".")
      else:
        if not buildSucceeded:
          self.echo(debug.ERROR, "B")
        elif exception:
          self.echo(debug.ERROR, "E")
        else:
          self.echo(debug.ERROR, "F")
        self.failedTests.append(result)

  def run(self, testNames):
    for testName in testNames:
      task = TestTask(self.config, testName)
      task.await(self.__testCallback)
      self.tasks.append(task)

  def waitForSummary(self):
    asynclib.JoinedAsyncTask(*self.tasks).wait()
    
    resultMap = {}

    with self.testResultLock:
      with open(os.path.join(self.config.TESTDIR, "test_result.json").replace("\\", "/"), 'wb') as fp:
        resultMap['num_tests'] = self.numTestsCompleted
        resultMap['failed_tests'] = []
        self.echo(debug.BOLD, "\n\n\nRan %s tests, " % (self.numTestsCompleted,))

        if len(self.failedTests) == 0:
          self.echo(debug.GREEN, "all succeeded!\n\n")
          json.dump(resultMap, fp)
          sys.exit(0)
        else:
          self.echo(debug.ERROR, "%s failed" % (len(self.failedTests),))
          self.echo(debug.BOLD, ".\n\nError summary:\n\n")

          for testName, buildSucceeded, exc_info, arg in self.failedTests:
            failedTestMap = {}
            failedTestMap['test_name'] = testName
            failedTestMap['build_succeeded'] = buildSucceeded
            failedTestMap['exception'] = False if exc_info is None else True
            self.echo(debug.BOLD, "  %s\n" % (testName,))
            if not buildSucceeded:
              proc, stdout, stderr = arg
              failedTestMap['proc'] = {}
              failedTestMap['proc']['returncode'] = proc.returncode
              failedTestMap['proc']['stdout'] = []
              failedTestMap['proc']['stderr'] = []
              self.echo(debug.ERROR, "    Build failed!\n")
              self.echo(debug.ERROR, "    stdout output:\n")
              for line in stdout:
                line = line.rstrip('\n')
                failedTestMap['proc']['stdout'].append(line)
                self.echo(debug.NORMAL, "      %s\n" % (line,))
              self.echo(debug.ERROR, "\n    stderr output:\n")
              for line in stderr:
                line = line.rstrip('\n')
                failedTestMap['proc']['stderr'].append(line)
                self.echo(debug.NORMAL, "      %s\n" % (line,))
              latexLogFile = ".build/%s/output.log" % (testName,)
              if os.path.exists(latexLogFile):
                failedTestMap['log_file'] = latexLogFile
                self.echo(debug.BOLD, "\n    see %s for more info.\n\n" % (latexLogFile,))
              else:
                self.echo(debug.BOLD, "\n\n")
            elif exc_info is not None:
              failedTestMap['exc_info'] = {}
              failedTestMap['exc_info']['type'] = str(exc_info[0])
              failedTestMap['exc_info']['value'] = str(exc_info[1])
              failedTestMap['exc_info']['traceback'] = []
              self.echo(debug.ERROR, "    Got exception %s: %s\n" % (exc_info[0], exc_info[1]))
              self.echo(debug.ERROR, "    Traceback:\n")
              for frame in traceback.format_tb(exc_info[2]):
                for line in frame.split('\n'):
                  line = line.rstrip('\n')
                  failedTestMap['exc_info']['traceback'].append(line)
                  self.echo(debug.NORMAL, "      %s\n" % (line,))
            else:
              failedPages = arg
              failedTestMap['failed_pages'] = failedPages
              failedPagesString = ", ".join(str(x) for x in failedPages)
              self.echo(debug.ERROR, "    Pages with diff: %s.\n\n" % (failedPagesString,))
            resultMap['failed_tests'].append(failedTestMap)

          self.echo(debug.BLUE, "PNGs containing diffs are available in '%s'\n\n" % (self.config.DIFFDIR,))
          json.dump(resultMap, fp)
          sys.exit(1)


def testGenerator(texTestsRootDir, testFilePrefix='test'):
  for dirPath, dirNames, fileNames in os.walk(texTestsRootDir):
    for fileName in fileNames:
      # Ignore files that contain spaces
      if " " in fileName:
        continue

      if not fileName.startswith(testFilePrefix):
        continue

      if not fileName.endswith(".tex"):
        continue

      filebasename = os.path.splitext(fileName)[0]
      test_name = os.path.relpath(os.path.join(dirPath, filebasename), texTestsRootDir).replace("\\", "/")

      yield test_name


class TestConfig():
  def __init__(self, testDir, numDotsPerLine=80, debugLevel=debug.INFO):
    testDir = os.path.relpath(os.path.realpath(testDir)).replace("\\", "/")
    assert os.path.isdir(testDir)

    self.TESTDIR     = testDir
    self.PDFSDIR     = os.path.join(testDir, "pdfs").replace("\\", "/")
    self.PROTODIR    = os.path.join(testDir, "proto").replace("\\", "/")
    self.TMPDIR      = os.path.join(testDir, "tmp").replace("\\", "/")
    self.DIFFDIR     = os.path.join(testDir, "diffs").replace("\\", "/")

    self.NUM_DOTS_PER_LINE = numDotsPerLine

    self.DEBUGLEVEL = debugLevel

    self.echoLock = threading.Lock()
    self.makeTaskSemaphore = threading.BoundedSemaphore(1)
    self.processPoolSemaphore = threading.BoundedSemaphore(8)


if __name__ == '__main__':
  if len(sys.argv) not in [2, 3]:
    print "Usage: %s <test base folder> [<test name>]" % sys.argv[0]
    sys.exit(1)

  testDir = sys.argv[1]
  texTestsRootDir = os.path.join(testDir, "tests").replace("\\", "/")

  config = TestConfig(testDir)
  runner = TestRunner(config)

  if len(sys.argv) == 3:
    testName = sys.argv[2]
    tests = [testName]
  else:
    tests = [tup for tup in testGenerator(texTestsRootDir)]

  runner.run(tests)
  runner.waitForSummary()
