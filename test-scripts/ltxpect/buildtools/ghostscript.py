import asyncio
from typing import Self, Type, TYPE_CHECKING

from ltxpect import asyncpopen
from ltxpect.coreabc import IExternalProgramLocator
from .abc import IPdfPageRasterizer


class GhostScriptPdfPageRasterizer:
    def __init__(self, gs_cmd: str) -> None:
        self.gs_cmd = gs_cmd

    async def convert_pdf_page_to_png_async(
        self, pdf_path: str, page_num: int, output_png_path: str
    ) -> None:
        gs_cmd_args = [
            self.gs_cmd,
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

        returncode, _stdout, _stderr = await asyncpopen.popen_async(
            asyncio.get_running_loop(),
            gs_cmd_args,
            timeout=2 * 60,
        )

        assert (
            returncode == 0
        ), f"Failed to generate PNG {output_png_path} from PDF {pdf_path} page {page_num}"

    @classmethod
    def create(cls: Type[Self], locator: IExternalProgramLocator) -> Self:
        gs_cmd = locator.find_program("GhostScript", ["gs", "gswin64c", "gswin32c"])
        return cls(gs_cmd)


if TYPE_CHECKING:
    _: type[IPdfPageRasterizer] = GhostScriptPdfPageRasterizer
