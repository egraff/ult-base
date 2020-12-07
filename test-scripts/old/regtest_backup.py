#!/usr/bin/env python

import os
import re
import sys
import json
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
  ERROR = "\\033[1;31m"
  FUCK = "\\033[1;41m"
  GREEN = "\\033[1;32m"
  WHITE = "\\033[1;37m"
dlvl = [debug.INFO, debug.DEBUG, debug.WARNING, debug.FUCK, debug.NORMAL, debug.WHITE, debug.GREEN, debug.YELLOW, debug.ERROR]


class TestPdfPagePair(asynclib.AsyncTask):
  def __init__(self, config, testPdfObj, protoPdfObj, pageNum, testName, texTestDir):
    self.pageNum = pageNum

    tmpDir = "%s/%s" % (config.TMPDIR, texTestDir)
    diffDir = "%s/%s" % (config.DIFFDIR, texTestDir)

    mkdirp(tmpDir)
    mkdirp(diffDir)

    self.testPngPagePath = "%s/%s_%s.png" % (tmpDir, testName, self.pageNum)
    self.protoPngPagePath = "%s/proto_%s_%s.png" % (tmpDir, testName, self.pageNum)
    self.diffPath = "%s/diff_%s_%s.png" % (diffDir, testName, self.pageNum)

    # Start processes for generating PNGs
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
    genPngProcs = results

    genTestPngProc, genProtoPngProc = genPngProcs
    assert genTestPngProc.returncode == 0, "Failed to generate PNG %s" % (self.testPngPagePath,)
    assert genProtoPngProc.returncode == 0, "Failed to generate PNG %s" % (self.protoPngPagePath,)

    task = ComparePngsAsyncTask(self.testPngPagePath, self.protoPngPagePath, self.diffPath)

    # Wait synchronously since we're already executing in separate thread
    task.wait()
    aeDiff = task.result

    self.__pngsAreEqual = (aeDiff == 0)

    if self.__pngsAreEqual:
      os.remove(self.testPngPagePath)
      os.remove(self.protoPngPagePath)
      os.remove(self.diffPath)

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
  def __init__(self, config, testName, texTestDir):
    self.testName = testName

    testPdfPath = "%s/%s/%s.pdf" % (config.PDFSDIR, texTestDir, testName)
    protoPdfPath = "%s/%s/%s.pdf" % (config.PROTODIR, texTestDir, testName)

    testPdfObj = PdfFile(testPdfPath)
    protoPdfObj = PdfFile(protoPdfPath)

    testPageList = determineListOfPagesToTest(testPdfObj)
    protoPageList = determineListOfPagesToTest(protoPdfObj)

    pageList = set(testPageList + protoPageList)

    self.failedPages = []

    testTasks = []
    for pageNum in pageList:
      if pageNum not in testPageList or pageNum not in protoPageList:
        self.failedPages.append(pageNum)
        continue

      task = TestPdfPagePair(config, testPdfObj, protoPdfObj, pageNum, testName, texTestDir)
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


def makeTestTask(config, testName, texTestDir):
  cmd = ['make', '-C', config.TESTDIR, '--no-print-directory', '_file', 'RETAINBUILDFLD=y', 'FILE=%s/%s.tex' % (texTestDir, testName)]
  task = asynclib.AsyncPopen(cmd, shell=False, env=os.environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  return task


class TestTask(asynclib.AsyncTask):
  def __init__(self, config, testName, texTestDir):
    self.config = config
    self.testName = testName
    self.texTestDir = texTestDir

    task = makeTestTask(config, self.testName, self.texTestDir)
    task.await(self._makeTaskComplete)
    self.wait = task.wait

  def _makeTaskComplete(self, proc):
    if proc.returncode != 0:
      self.__result = (self.testName, False, proc)
      return

    task = TestPdfPair(self.config, self.testName, self.texTestDir)
    task.wait()
    _, failedPages = task.result

    testPassed = (len(failedPages) == 0)

    self.__result = (self.testName, True, failedPages)

  # Result is on the form
  #  (test name, Build succeeded = TRUE, list of failed pages)
  # or
  #  (test name, Build succeeded = FALSE, build proc)
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

    s = "sh -c \"printf \\\"" + color + " ".join([str(x).replace("\n", "\\n") for x in string]) + "\\033[0m\\\"\""
    asynclib.AsyncPopen(s, shell=True).wait()

  def __testCallback(self, result):
    testName, buildSucceeded, failedPages = result
    testPassed = buildSucceeded and (len(failedPages) == 0)

    with self.testResultLock:
      if self.numTestsCompleted % self.config.NUM_DOTS_PER_LINE == 0:
        self.echo(debug.WHITE, "\n")

      self.numTestsCompleted += 1

      if testPassed:
        self.echo(debug.GREEN, ".")
      else:
        self.echo(debug.ERROR, "F" if buildSucceeded else "B")
        self.failedTests.append(result)

  def run(self, testNames):
    for testName, texTestDir in testNames:
      task = TestTask(self.config, testName, texTestDir)
      task.await(self.__testCallback)
      self.tasks.append(task)

  def waitForSummary(self):
    asynclib.JoinedAsyncTask(*self.tasks).wait()
    
    resultMap = {}

    with self.testResultLock:
      with open(os.path.join(self.config.TESTDIR, "test_result.json").replace("\\", "/"), 'wb') as fp:
        resultMap['num_tests'] = self.numTestsCompleted
        resultMap['failed_tests'] = []
        self.echo(debug.WHITE, "\n\n\nRan %s tests, " % (self.numTestsCompleted,))

        if len(self.failedTests) == 0:
          self.echo(debug.GREEN, "all succeeded!\n\n")
          json.dump(resultMap, fp)
          sys.exit(0)
        else:
          self.echo(debug.ERROR, "%s failed" % (len(self.failedTests),))
          self.echo(debug.WHITE, ".\n\nError summary:\n\n")

          for testName, buildSucceeded, arg in self.failedTests:
            failedTestMap = {}
            failedTestMap['test_name'] = testName
            failedTestMap['build_succeeded'] = buildSucceeded
            self.echo(debug.WHITE, "  %s\n" % (testName,))
            if not buildSucceeded:
              proc = arg
              failedTestMap['proc'] = {}
              failedTestMap['proc']['returncode'] = proc.returncode
              failedTestMap['proc']['stdout'] = []
              failedTestMap['proc']['stderr'] = []
              self.echo(debug.ERROR, "    Build failed!\n")
              self.echo(debug.ERROR, "    stdout output:\n")
              for line in proc.stdout:
                line = line.rstrip('\n')
                failedTestMap['proc']['stdout'].append(line)
                self.echo(debug.NORMAL, "      %s\n" % (line,))
              self.echo(debug.ERROR, "\n    stderr output:\n")
              for line in proc.stderr:
                line = line.rstrip('\n')
                failedTestMap['proc']['stderr'].append(line)
                self.echo(debug.NORMAL, "      %s\n" % (line,))
              latexLogFile = ".build/%s/output.log" % (testName,)
              if os.path.exists(latexLogFile):
                failedTestMap['log_file'] = latexLogFile
                self.echo(debug.WHITE, "\n    see %s for more info.\n\n" % (latexLogFile,))
              else:
                self.echo(debug.WHITE, "\n\n")
            else:
              failedPages = arg
              failedTestMap['failed_pages'] = failedPages
              failedPagesString = ", ".join(str(x) for x in failedPages)
              self.echo(debug.ERROR, "    Pages with diff: %s.\n\n" % (failedPagesString,))
            resultMap['failed_tests'].append(failedTestMap)

          self.echo(debug.YELLOW, "PNGs containing diffs are available in '%s'\n\n" % (self.config.DIFFDIR,))
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

      yield (os.path.splitext(fileName)[0], os.path.relpath(dirPath, texTestsRootDir))


class TestConfig():
  def __init__(self, testDir, numDotsPerLine=80, debugLevel=debug.INFO):
    testDir = os.path.relpath(os.path.realpath(testDir))
    assert os.path.isdir(testDir)

    self.TESTDIR     = testDir
    self.PDFSDIR     = os.path.join(testDir, "pdfs").replace("\\", "/")
    self.PROTODIR    = os.path.join(testDir, "proto").replace("\\", "/")
    self.TMPDIR      = os.path.join(testDir, "tmp").replace("\\", "/")
    self.DIFFDIR     = os.path.join(testDir, "diffs").replace("\\", "/")

    self.NUM_DOTS_PER_LINE = numDotsPerLine

    self.DEBUGLEVEL = debugLevel


if __name__ == '__main__':
  if len(sys.argv) != 2:
    print "Usage: %s <test base folder>" % sys.argv[0]
    sys.exit(1)

  testDir = sys.argv[1]
  texTestsRootDir = os.path.join(testDir, "tests").replace("\\", "/")

  config = TestConfig(testDir)
  runner = TestRunner(config)
  runner.run(testGenerator(texTestsRootDir))
  runner.waitForSummary()
