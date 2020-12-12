import asyncio
import os
import re
import errno
import subprocess
from typing import Awaitable, List, Tuple

import asynclib
import testenv

GS = testenv.find_ghostscript()
CMP = testenv.find_compare()
IDENT = testenv.find_identify()
PDFINFO = testenv.find_pdfinfo()


DEFAULT_UTIL_TIMEOUT = 2 * 60


def mkdirp(path):
    try:
        os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            raise


def _convert_pdf_page_to_png_async(
    pdf_path: str, page_num: int, output_png_path: str
) -> Awaitable[Tuple[int, List[str], List[str]]]:
    gs_cmd = [
        GS,
        "-q",
        "-dQUIET",
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-dNOPROMPT",
        "-sDEVICE=png16m",
        "-dPDFUseOldCMS=false",
        "-dMaxBitmap=500000000",
        "-dAlignToPixels=0",
        "-dGridFitTT=2",
        "-r150",
        "-o",
        output_png_path,
        "-dFirstPage=%s" % page_num,
        "-dLastPage=%s" % page_num,
        pdf_path,
    ]

    return asynclib.popen_async(
        gs_cmd, timeout=DEFAULT_UTIL_TIMEOUT, raise_exception_on_timeout=True
    )


async def get_png_size_async(png_path) -> Awaitable[Tuple[int, int]]:
    identify_cmd = [IDENT, "-format", "%G", png_path]
    returncode, stdout, _stderr = await asynclib.popen_async(
        identify_cmd, timeout=DEFAULT_UTIL_TIMEOUT, raise_exception_on_timeout=True
    )

    assert returncode <= 1

    match = re.match(r"^(\d+)x(\d+)$", stdout[0].decode("ascii"))
    assert match is not None

    # Result is (width, height)
    return tuple(int(x) for x in match.groups())


async def compare_pngs_async(
    png_path_first: str, png_path_second: str, output_diff_path: str
) -> Awaitable[int]:
    cmp_cmd = [
        CMP,
        "-metric",
        "ae",
        png_path_first,
        png_path_second,
        "PNG24:%s" % output_diff_path,
    ]
    returncode, _stdout, stderr = await asynclib.popen_async(
        cmp_cmd, timeout=DEFAULT_UTIL_TIMEOUT, raise_exception_on_timeout=True
    )

    assert returncode <= 1

    # Needed because stderr[0] could be something like "1.33125e+006"
    result = int(float(stderr[0]))

    # Result is diff (0 means equal)
    return result


class PdfFile(object):
    def __init__(self, path: str, num_pages: int):
        self._path = path
        self._num_pages = num_pages

    @classmethod
    async def create(cls, path: str):
        if not os.path.exists(path):
            raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), path)

        num_pages = await cls._determine_num_pages_in_pdf_async(path)
        return cls(path, num_pages)

    @staticmethod
    async def _determine_num_pages_in_pdf_async(path: str) -> Awaitable[int]:
        # use pdfinfo to extract number of pages in pdf file
        returncode, stdout, _stderr = await asynclib.popen_async(
            [PDFINFO, path],
            timeout=DEFAULT_UTIL_TIMEOUT,
            raise_exception_on_timeout=True,
        )

        assert returncode <= 1

        output = b"\n".join(stdout).decode("utf-8")
        pages = re.findall(r"\d+", re.search(r"Pages:.*", output).group())[0]
        return int(pages)

    @property
    def path(self) -> str:
        return self._path

    @property
    def num_physical_pages(self) -> int:
        return self._num_pages

    # Generate PNG for given page number in PDF
    async def get_png_for_page_async(
        self, page_num: int, output_png_path: str
    ) -> Awaitable[Tuple[int, List[str], List[str]]]:
        assert page_num >= 1
        assert page_num <= self._num_pages

        return await _convert_pdf_page_to_png_async(
            self.path, page_num, output_png_path
        )
