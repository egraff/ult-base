import asyncio
import re
from dataclasses import dataclass
from typing import Self, Type, TYPE_CHECKING

from ltxpect import asyncpopen
from ltxpect.coreabc import IExternalProgramLocator
from .abc import IPdfDocInfo, IPdfDocInfoProvider


@dataclass(frozen=True, slots=True, kw_only=True)
class PdfDocInfo:
    path: str
    num_physical_pages: int


class PdfDocInfoProviderUsingExternalPdfInfoProgram:
    def __init__(self, pdfinfo_cmd: str) -> None:
        self.pdfinfo_cmd = pdfinfo_cmd

    async def get_pdf_info_async(self, pdf_path: str) -> IPdfDocInfo:
        # use pdfinfo to extract number of pages in pdf file
        returncode, stdout, _stderr = await asyncpopen.popen_async(
            asyncio.get_running_loop(),
            [self.pdfinfo_cmd, pdf_path],
            timeout=2 * 60,
        )

        assert returncode <= 1

        output = b"\n".join(stdout).decode("utf-8")

        pages_match = re.search(r"Pages:.*", output)
        assert pages_match is not None

        num_pages = int(re.findall(r"\d+", pages_match.group())[0])

        return PdfDocInfo(path=pdf_path, num_physical_pages=num_pages)

    @classmethod
    def create(cls: Type[Self], locator: IExternalProgramLocator) -> Self:
        pdfinfo_cmd = locator.find_program("PDFInfo", ["pdfinfo"])
        return cls(pdfinfo_cmd)


if TYPE_CHECKING:
    _: type[IPdfDocInfo] = PdfDocInfo  # type: ignore[no-redef]
    _: type[IPdfDocInfoProvider] = PdfDocInfoProviderUsingExternalPdfInfoProgram  # type: ignore[no-redef]
