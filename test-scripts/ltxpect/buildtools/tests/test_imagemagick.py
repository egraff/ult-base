import asyncio
import sys
import unittest
import unittest.mock as mock
from typing import Any, cast, Mapping

from ltxpect import asyncpopen
from ltxpect.buildtools.imagemagick import ImageMagickPngImageComparer


class ImageMagickPngImageComparerTests(unittest.TestCase):
    def setUp(self) -> None:
        if sys.platform == "win32":
            self.loop = asyncio.ProactorEventLoop()
        else:
            self.loop = asyncio.SelectorEventLoop()

        patcher = mock.patch.object(
            asyncpopen, "popen_async", new_callable=mock.AsyncMock
        )
        self.popen_async_mock = patcher.start()
        self.addCleanup(patcher.stop)

        self.popen_async_called_future = cast(
            asyncio.Future[tuple[list[str], float, Mapping[str, str] | None]],
            self.loop.create_future(),
        )

        self.popen_async_result_future = cast(
            asyncio.Future[asyncpopen.AsyncPopenResult],
            self.loop.create_future(),
        )

        async def popen_async(
            loop: asyncio.AbstractEventLoop,
            args: list[str],
            timeout: float = 0,
            env: Mapping[str, str] | None = None,
        ) -> asyncpopen.AsyncPopenResult:
            self.popen_async_called_future.set_result((args, timeout, env))

            result = await self.popen_async_result_future
            return result

        self.popen_async_mock.side_effect = popen_async

    async def _call_compare_and_wait_for_result(
        self,
        comparer: ImageMagickPngImageComparer,
        png_path_first: str,
        png_path_second: str,
        output_diff_path: str,
    ) -> asyncio.Future[bool]:
        compare_task = cast(
            asyncio.Task[bool],
            asyncio.create_task(
                comparer.compare_png_images_async(
                    png_path_first, png_path_second, output_diff_path
                )
            ),
        )

        # Use asyncio.wait() in case there was an exception from popen_async()
        done_futures, _ = await asyncio.wait(
            cast(
                list[asyncio.Future[Any]],
                [self.popen_async_called_future, compare_task],
            ),
            return_when=asyncio.FIRST_COMPLETED,
            timeout=1.0,
        )
        if compare_task in done_futures:
            await compare_task
            self.fail("compare_png_images_async() returned unexpectedly")

        _ = await self.popen_async_called_future

        return compare_task

    def test_imagemagick_7_0_compare_ae_output__images_with_no_diff(self):
        # Arrange

        async def test_async():
            comparer = ImageMagickPngImageComparer(["compare"])

            compare_result_future = await self._call_compare_and_wait_for_result(
                comparer, "first_png", "second_png", "output_diff_png"
            )

            # Act

            self.popen_async_result_future.set_result(
                asyncpopen.AsyncPopenResult(returncode=0, stdout=[], stderr=[b"0"])
            )

            # Assert

            compare_result = await compare_result_future
            self.assertTrue(compare_result)

        try:
            self.loop.run_until_complete(asyncio.wait_for(test_async(), timeout=1.0))
        finally:
            self.loop.close()

    def test_imagemagick_7_0_compare_ae_output__images_with_diff(self):
        # Arrange

        async def test_async():
            comparer = ImageMagickPngImageComparer(["compare"])

            compare_result_future = await self._call_compare_and_wait_for_result(
                comparer, "first_png", "second_png", "output_diff_png"
            )

            # Act

            self.popen_async_result_future.set_result(
                asyncpopen.AsyncPopenResult(returncode=0, stdout=[], stderr=[b"1579"])
            )

            # Assert

            compare_result = await compare_result_future
            self.assertFalse(compare_result)

        try:
            self.loop.run_until_complete(asyncio.wait_for(test_async(), timeout=1.0))
        finally:
            self.loop.close()

    def test_imagemagick_7_1_compare_ae_output__images_with_no_diff(self):
        # Arrange

        async def test_async():
            comparer = ImageMagickPngImageComparer(["compare"])

            compare_result_future = await self._call_compare_and_wait_for_result(
                comparer, "first_png", "second_png", "output_diff_png"
            )

            # Act

            self.popen_async_result_future.set_result(
                asyncpopen.AsyncPopenResult(returncode=0, stdout=[], stderr=[b"0 (0)"])
            )

            # Assert

            compare_result = await compare_result_future
            self.assertTrue(compare_result)

        try:
            self.loop.run_until_complete(asyncio.wait_for(test_async(), timeout=1.0))
        finally:
            self.loop.close()

    def test_imagemagick_7_1_compare_ae_output__images_with_diff(self):
        # Arrange

        async def test_async():
            comparer = ImageMagickPngImageComparer(["compare"])

            compare_result_future = await self._call_compare_and_wait_for_result(
                comparer, "first_png", "second_png", "output_diff_png"
            )

            # Act

            self.popen_async_result_future.set_result(
                asyncpopen.AsyncPopenResult(
                    returncode=0, stdout=[], stderr=[b"1.0348e+08 (1579)"]
                )
            )

            # Assert

            compare_result = await compare_result_future
            self.assertFalse(compare_result)

        try:
            self.loop.run_until_complete(asyncio.wait_for(test_async(), timeout=1.0))
        finally:
            self.loop.close()
