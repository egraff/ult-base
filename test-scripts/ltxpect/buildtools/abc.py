from typing import Awaitable, Protocol, NamedTuple

from ltxpect import asyncpopen


class ImageDimensions(NamedTuple):
    width: int
    height: int


class IPngImageDimensionsInspector(Protocol):
    def get_png_image_dimensions_async(
        self, png_path: str
    ) -> Awaitable[ImageDimensions]: ...


class IPngImageComparer(Protocol):
    def compare_png_images_async(
        self, png_path_first: str, png_path_second: str, output_diff_path: str
    ) -> Awaitable[bool]: ...


class ILatexDocumentBuildTool(Protocol):
    def build_latex_document_async(
        self,
        base_dir: str,
        texfile_dir_subpath: str,
        texfile_filename: str,
        latex_build_dir_subpath: str,
        latex_jobname: str,
        timeout: float = 0,
    ) -> Awaitable[asyncpopen.AsyncPopenResult]: ...


class IPdfDocInfo(Protocol):
    @property
    def path(self) -> str: ...

    @property
    def num_physical_pages(self) -> int: ...


class IPdfDocInfoProvider(Protocol):
    def get_pdf_info_async(self, pdf_path: str) -> Awaitable[IPdfDocInfo]: ...


class IPdfPageRasterizer(Protocol):
    def convert_pdf_page_to_png_async(
        self, pdf_path: str, page_num: int, output_png_path: str
    ) -> Awaitable[None]: ...
