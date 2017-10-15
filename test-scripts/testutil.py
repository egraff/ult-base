#!/usr/bin/env python

import os
import re
import errno
import subprocess

import testenv
import asynclib

GS = testenv.getGhostScript()
CMP = testenv.getCompare()
PDFINFO = testenv.getPDFInfo()


def mkdirp(path):
  try:
    os.makedirs(path)
  except OSError:
    if not os.path.isdir(path):
      raise


def _convertPdfPageToPngAsync(pdfPath, pageNum, outputPngPath):
  gsCmd = [
            GS, '-q', '-dQUIET', '-dSAFER', '-dBATCH', '-dNOPAUSE', '-dNOPROMPT',
            '-sDEVICE=png16m', '-dPDFUseOldCMS=false',
            '-dMaxBitmap=500000000', '-dAlignToPixels=0', '-dGridFitTT=2', '-r150',
            '-o', outputPngPath, '-dFirstPage=%s' % pageNum,
            '-dLastPage=%s' % pageNum, pdfPath
          ]

  task = asynclib.AsyncPopen(gsCmd, shell=False, env=os.environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  return task


class ComparePngsAsyncTask(asynclib.AsyncTask):
  def __init__(self, pngPathFirst, pngPathSecond, outputDiffPath):
    cmpCmd = [CMP, '-metric', 'ae', pngPathFirst, pngPathSecond, 'PNG24:%s' % outputDiffPath]
    self.__cmpProc = subprocess.Popen(cmpCmd, shell=False, env=os.environ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  def wait(self):
    _stdout, stderr = self.__cmpProc.communicate()
    self.__cmpProc.wait()
    lines = stderr.splitlines()
    assert self.__cmpProc.returncode <= 1

    # Needed because lines[0] could be something like "1.33125e+006"
    self.__result = int(float(lines[0]))

  # Result is diff (0 means equal)
  @property
  def result(self):
    return self.__result


class PdfFile(object):
  def __init__(self, path):
    if not os.path.exists(path):
      raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), path)

    self.path = path
    self.__determineNumPagesInPdf()

  def __determineNumPagesInPdf(self):
    # use pdfinfo to extract number of pages in pdf file
    output = subprocess.check_output([PDFINFO, self.path])
    pages = re.findall(r"\d+", re.search(r"Pages:.*", output).group())[0]

    self.__numPages = int(pages)

  def numPhysicalPages(self):
    return self.__numPages

  # Generate PNG for given page number in PDF
  def getPngForPageAsync(self, pageNum, outputPngPath):
    assert pageNum >= 1
    assert pageNum <= self.numPhysicalPages()

    return _convertPdfPageToPngAsync(self.path, pageNum, outputPngPath)

  # Generate PNG for given page number in PDF
  def getPngForPage(self, pageNum, outputPngPath, callback):
    task = self.getPngForPageAsync(pageNum, outputPngPath)
    task.await(callback)
