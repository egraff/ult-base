import asyncio
import re
from collections.abc import Sequence
from typing import Self, Type, TYPE_CHECKING

from ltxpect import asyncpopen
from ltxpect.coreabc import IExternalProgramLocator
from .abc import ImageDimensions, IPngImageComparer, IPngImageDimensionsInspector


class ImageMagickPngImageComparer:
    def __init__(self, im_compare_cmd: Sequence[str]) -> None:
        self.im_compare_cmd = tuple(im_compare_cmd)

    async def compare_png_images_async(
        self, png_path_first: str, png_path_second: str, output_diff_path: str
    ) -> bool:
        cmd_args = list(self.im_compare_cmd) + [
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

        assert len(stderr) >= 0
        compare_output = stderr[0].decode("ascii")

        # NOTE: compare from ImageMagick <= 7.0 returns a single value for the 'ae' metric, whereas in
        # ImageMagick >= 7.1, the output is like 'AAA (BBB)'. However, due to bugs/changes, the output has also
        # changed between ImageMagick 7.1.1 and 7.1.2. In 7.1.1, 'BBB' is the same value that used to be output when
        # it was a single value, but in 7.1.2 it seems that the two value have been flipped.
        match = re.match(
            r"^(?P<first>\S+)(?: \((?P<second>[^\)\s]+)\))?$", compare_output
        )
        assert match is not None

        if match["second"]:
            # NOTE: the float conversion is needed because the output value could be something like "1.33125e+006"
            ae_diff = int(max(float(match["first"]), float(match["second"])))
        else:
            # NOTE: the float conversion is needed because the output value could be something like "1.33125e+006"
            ae_diff = int(float(match["first"]))

        # (0 means equal)
        return ae_diff == 0

    @classmethod
    def create(cls: Type[Self], locator: IExternalProgramLocator) -> Self:
        im_compare_cmd = locator.find_program("Compare (ImageMagick)", ["compare"])
        return cls([im_compare_cmd])


class ImageMagickPngImageDimensionsInspector:
    def __init__(self, im_identify_cmd: Sequence[str]) -> None:
        self.im_identify_cmd = tuple(im_identify_cmd)

    async def get_png_image_dimensions_async(self, img_path: str) -> ImageDimensions:
        returncode, stdout, _stderr = await asyncpopen.popen_async(
            asyncio.get_running_loop(),
            list(self.im_identify_cmd) + ["-format", "%G", img_path],
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
        return cls([im_identify_cmd])


if TYPE_CHECKING:
    _: type[IPngImageComparer] = ImageMagickPngImageComparer  # type: ignore[no-redef]
    _: type[IPngImageDimensionsInspector] = ImageMagickPngImageDimensionsInspector  # type: ignore[no-redef]
