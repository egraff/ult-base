import asyncio
import re
from typing import Self, Type, TYPE_CHECKING

from ltxpect import asyncpopen
from ltxpect.coreabc import IExternalProgramLocator
from .abc import ImageDimensions, IPngImageComparer, IPngImageDimensionsInspector


class ImageMagickPngImageComparer:
    def __init__(self, im_compare_cmd: str) -> None:
        self.im_compare_cmd = im_compare_cmd

    async def compare_png_images_async(
        self, png_path_first: str, png_path_second: str, output_diff_path: str
    ) -> bool:
        cmd_args = [
            self.im_compare_cmd,
            "-metric",
            "ae",
            png_path_first,
            png_path_second,
            f"PNG24:{output_diff_path}",
        ]

        returncode, _stdout, stderr = await asyncpopen.popen_async(
            asyncio.get_running_loop(), cmd_args, timeout=2 * 60
        )

        assert returncode <= 1

        # Needed because stderr[0] could be something like "1.33125e+006"
        ae_diff = int(float(stderr[0]))

        # (0 means equal)
        return ae_diff == 0

    @classmethod
    def create(cls: Type[Self], locator: IExternalProgramLocator) -> Self:
        im_compare_cmd = locator.find_program("Compare (ImageMagick)", ["compare"])
        return cls(im_compare_cmd)


class ImageMagickPngImageDimensionsInspector:
    def __init__(self, im_identify_cmd: str) -> None:
        self.im_identify_cmd = im_identify_cmd

    async def get_png_image_dimensions_async(self, img_path: str) -> ImageDimensions:
        returncode, stdout, _stderr = await asyncpopen.popen_async(
            asyncio.get_running_loop(),
            [self.im_identify_cmd, "-format", "%G", img_path],
            timeout=2 * 60,
        )

        assert returncode <= 1

        match = re.match(r"^(\d+)x(\d+)$", stdout[0].decode("ascii"))
        assert match is not None

        # Result is (width, height)
        return ImageDimensions(*tuple(int(x) for x in match.groups()))

    @classmethod
    def create(cls: Type[Self], locator: IExternalProgramLocator) -> Self:
        im_identify_cmd = locator.find_program("Identify (ImageMagick)", ["identify"])
        return cls(im_identify_cmd)


if TYPE_CHECKING:
    _: type[IPngImageComparer] = ImageMagickPngImageComparer  # type: ignore[no-redef]
    _: type[IPngImageDimensionsInspector] = ImageMagickPngImageDimensionsInspector  # type: ignore[no-redef]
