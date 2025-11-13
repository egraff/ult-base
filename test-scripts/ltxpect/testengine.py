import asyncio
import os
import re
import sys
from types import TracebackType
from typing import cast, Sequence, Type, TYPE_CHECKING

from . import asyncpopen
from .buildtools.abc import (
    ILatexDocumentBuildTool,
    IPdfDocInfo,
    IPdfDocInfoProvider,
    IPdfPageRasterizer,
    IPngImageComparer,
    IPngImageDimensionsInspector,
)
from .coreabc import IFileSystem, IPathUtil, ITestEngine, ITestRunContext
from .testconfig import TestConfig
from .testresult import TestResult


class TestEngineContext:
    def __init__(
        self,
        config: TestConfig,
        path_util: IPathUtil,
        fs: IFileSystem,
        pdf_doc_info_provider: IPdfDocInfoProvider,
        pdf_page_rasterizer: IPdfPageRasterizer,
        png_dimensions_inspector: IPngImageDimensionsInspector,
        png_comparer: IPngImageComparer,
    ) -> None:
        self.config = config
        self.path_util = path_util
        self.fs = fs
        self.pdf_doc_info_provider = pdf_doc_info_provider
        self.pdf_page_rasterizer = pdf_page_rasterizer
        self.png_dimensions_inspector = png_dimensions_inspector
        self.png_comparer = png_comparer

        test_base_dir = path_util.path_relpath(fs.resolve_path(config.test_base_dir))
        assert fs.is_directory(test_base_dir)

        self.TEST_BASE_DIR = test_base_dir
        self.BUILDDIR = path_util.path_join(test_base_dir, ".build")
        self.TESTSDIR = path_util.path_join(test_base_dir, "tests")
        self.PDFSDIR = path_util.path_join(test_base_dir, "pdfs")
        self.PROTODIR = path_util.path_join(test_base_dir, config.proto_dir)
        self.TMPDIR = path_util.path_join(test_base_dir, "tmp")
        self.DIFFDIR = path_util.path_join(test_base_dir, "diffs")

        self.make_task_semaphore = asyncio.BoundedSemaphore(1)
        self.process_pool_semaphore = asyncio.BoundedSemaphore(
            config.num_concurrent_processes
        )

        self.latex_build_timeout = 3 * 60


async def test_pdf_page_pair_async(
    ctx: TestEngineContext,
    test_pdf_info: IPdfDocInfo,
    proto_pdf_info: IPdfDocInfo,
    page_num: int,
    test_name: str,
) -> tuple[int, bool]:
    assert page_num >= 1
    assert page_num <= test_pdf_info.num_physical_pages
    assert page_num <= proto_pdf_info.num_physical_pages

    path_util = ctx.path_util
    fs = ctx.fs
    pdf_page_rasterizer = ctx.pdf_page_rasterizer
    png_dimensions_inspector = ctx.png_dimensions_inspector
    png_comparer = ctx.png_comparer

    png_relpath = "{}_{}.png".format(test_name, page_num)
    test_png_page_path = path_util.path_join(ctx.TMPDIR, "tests", png_relpath)
    proto_png_page_path = path_util.path_join(ctx.TMPDIR, "proto", png_relpath)
    diff_path = path_util.path_join(ctx.DIFFDIR, png_relpath)

    fs.mkdirp(os.path.dirname(test_png_page_path))
    fs.mkdirp(os.path.dirname(proto_png_page_path))
    fs.mkdirp(os.path.dirname(diff_path))

    # Start processes for generating PNGs
    async with ctx.process_pool_semaphore:
        test_pdf_future = asyncio.ensure_future(
            pdf_page_rasterizer.convert_pdf_page_to_png_async(
                test_pdf_info.path, page_num, test_png_page_path
            )
        )
        proto_pdf_future = asyncio.ensure_future(
            pdf_page_rasterizer.convert_pdf_page_to_png_async(
                proto_pdf_info.path, page_num, proto_png_page_path
            )
        )

        done_futures, pending_futures = await asyncio.wait(
            [test_pdf_future, proto_pdf_future]
        )
        assert len(pending_futures) == 0

        gen_test_png_future, gen_proto_png_future = done_futures

        try:
            await gen_test_png_future
            await gen_proto_png_future
        except:
            # Observe all exceptions to suppress "Task exception was never retrieved" error
            # (we are only interested in the first exception)
            _ = [x.exception() for x in done_futures]

            # Re-raise just the first exception
            raise

        # FIXME: should probably have chained each png task to each png size task, but getting the image sizes should be quick...
        test_png_dim = await png_dimensions_inspector.get_png_image_dimensions_async(
            test_png_page_path
        )
        proto_png_dim = await png_dimensions_inspector.get_png_image_dimensions_async(
            proto_png_page_path
        )

        if test_png_dim != proto_png_dim:
            return page_num, False

        pngs_are_equal = await png_comparer.compare_png_images_async(
            test_png_page_path, proto_png_page_path, diff_path
        )

        if pngs_are_equal:
            fs.remove_file(test_png_page_path)
            fs.remove_file(proto_png_page_path)
            fs.remove_file(diff_path)

    return (page_num, pngs_are_equal)


# Use file name of PDF to determine which pages we want to test
def determine_list_of_pages_to_test(pdf_info: IPdfDocInfo) -> tuple[int, ...]:
    num_pages = pdf_info.num_physical_pages
    basename = os.path.basename(pdf_info.path)
    noext = os.path.splitext(basename)[0]

    # search for a range in filename ( denoted with [ ] ) and save only the range
    textrange_match = re.search(r"\[.*\]", noext)
    if textrange_match is not None:
        # remove brackets and commas
        textrange = re.sub(r"([\[\]])", r"", textrange_match.group()).replace(r",", " ")

        page_list: list[int] = []

        # make list and translate hyphen into a sequence, e.g 3-6 -> "3 4 5 6"
        for num in textrange.split(" "):
            if "-" in num:
                numrange_str_list = num.split("-")
                assert len(numrange_str_list) == 2

                numrange = range(
                    int(numrange_str_list[0]), int(numrange_str_list[1]) + 1
                )
                page_list.extend(numrange)
            else:
                page_list.append(int(num))

        page_list = sorted(set(page_list))

        for page_num in page_list:
            assert (
                page_num <= num_pages
            ), f"{page_num} (from '{basename}' -> {page_list}) not <= {num_pages}"
    else:
        page_list = list(range(1, num_pages + 1))

    return tuple(page_list)


async def test_pdf_pair_async(
    ctx: TestEngineContext, test_name: str, test_pdf_path: str, proto_pdf_path: str
) -> tuple[str, tuple[int, ...]]:
    async with ctx.process_pool_semaphore:
        test_pdf_info = await ctx.pdf_doc_info_provider.get_pdf_info_async(
            test_pdf_path
        )
        proto_pdf_info = await ctx.pdf_doc_info_provider.get_pdf_info_async(
            proto_pdf_path
        )

    test_page_list = determine_list_of_pages_to_test(test_pdf_info)
    proto_page_list = determine_list_of_pages_to_test(proto_pdf_info)

    page_list = set(test_page_list + proto_page_list)

    failed_pages: list[int] = []

    test_futures: list[asyncio.Future[tuple[int, bool]]] = []
    for page_num in page_list:
        if page_num not in test_page_list or page_num not in proto_page_list:
            failed_pages.append(page_num)
            continue

        test_pdf_pair_future = asyncio.ensure_future(
            test_pdf_page_pair_async(
                ctx, test_pdf_info, proto_pdf_info, page_num, test_name
            )
        )
        test_futures.append(test_pdf_pair_future)

    done_futures, pending_futures = await asyncio.wait(test_futures)
    assert len(pending_futures) == 0

    for png_future in done_futures:
        try:
            page_num, pngs_are_equal = await png_future
        except:
            # Observe all exceptions to suppress "Task exception was never retrieved" error
            # (we are only interested in the first exception)
            _ = [x.exception() for x in done_futures]

            # Re-raise just the first exception
            raise

        if not pngs_are_equal:
            failed_pages.append(page_num)

    failed_pages.sort()

    # Result is on the form (testname, list of failed pages)
    return (test_name, tuple(failed_pages))


class TestEngine:
    def __init__(
        self,
        config: TestConfig,
        path_util: IPathUtil,
        fs: IFileSystem,
        latex_doc_buildtool: ILatexDocumentBuildTool,
        pdf_doc_info_provider: IPdfDocInfoProvider,
        pdf_page_rasterizer: IPdfPageRasterizer,
        png_dimensions_inspector: IPngImageDimensionsInspector,
        png_comparer: IPngImageComparer,
    ) -> None:
        self.config = config
        self.path_util = path_util
        self.fs = fs
        self.latex_doc_buildtool = latex_doc_buildtool
        self.pdf_doc_info_provider = pdf_doc_info_provider
        self.pdf_page_rasterizer = pdf_page_rasterizer
        self.png_dimensions_inspector = png_dimensions_inspector
        self.png_comparer = png_comparer

    def create_test_run_context(self) -> ITestRunContext:
        """Create a test run context for a new test run."""
        return TestEngineContext(
            self.config,
            self.path_util,
            self.fs,
            self.pdf_doc_info_provider,
            self.pdf_page_rasterizer,
            self.png_dimensions_inspector,
            self.png_comparer,
        )

    async def prepare_test_run_async(
        self, ctx: ITestRunContext, test_names: Sequence[str]
    ) -> None:
        """Prepare a new test run. Called once at the start of the test run,
        before run_test_async() is invoked for each test.
        """

    async def run_warmup_compile_for_test_async(
        self, ctx: ITestRunContext, test_name: str
    ) -> None:
        """Run a pre-test warmup compile step."""

        assert isinstance(ctx, TestEngineContext)

        latex_jobname = "output"

        # Path to tex file, relative to ctx.TESTSDIR
        texfile_relpath = "{}.tex".format(test_name)

        texfile_parent_dir_relpath = os.path.dirname(texfile_relpath)
        texfile_filename = os.path.basename(texfile_relpath)
        texfile_basename = os.path.splitext(texfile_filename)[0]

        # Certain LaTeX versions have problems with build directory paths containing '[' and ']' characters
        # when going through MSYS->Windows path substitution
        texfile_basename_subst = (
            texfile_basename.replace("]", "").replace("[", "~").replace(",", "_")
            if re.search(r"\[.*\]", texfile_basename)
            else texfile_basename
        )

        texfile_parent_dir_path = self.path_util.path_join(
            ctx.TESTSDIR, texfile_parent_dir_relpath
        )
        assert self.fs.is_directory(texfile_parent_dir_path)
        assert self.fs.is_file(
            self.path_util.path_join(texfile_parent_dir_path, texfile_filename)
        )

        latex_build_dir = self.path_util.path_join(
            ctx.BUILDDIR, texfile_parent_dir_relpath, texfile_basename_subst
        )

        self.fs.force_remove_tree(latex_build_dir)
        self.fs.mkdirp(latex_build_dir)

        texfile_parent_dir_relative_to_base_dir = self.path_util.path_relpath(
            texfile_parent_dir_path, ctx.TEST_BASE_DIR
        )
        latex_build_dir_relative_to_base_dir = self.path_util.path_relpath(
            latex_build_dir, ctx.TEST_BASE_DIR
        )
        for _ in range(2):
            try:
                _ = await self.latex_doc_buildtool.build_latex_document_async(
                    base_dir=ctx.TEST_BASE_DIR,
                    texfile_parent_dir_subpath=texfile_parent_dir_relative_to_base_dir,
                    texfile_filename=texfile_filename,
                    latex_build_dir_subpath=latex_build_dir_relative_to_base_dir,
                    latex_jobname=latex_jobname,
                    timeout=ctx.latex_build_timeout,
                )
            except asyncio.CancelledError:
                raise
            except:
                pass

        self.fs.force_remove_tree(latex_build_dir)

    async def run_test_async(self, ctx: ITestRunContext, test_name: str) -> TestResult:
        """Execute the specified test case."""

        assert isinstance(ctx, TestEngineContext)

        test_pdf_path = self.path_util.path_join(
            ctx.PDFSDIR, "{}.pdf".format(test_name)
        )
        proto_pdf_path = self.path_util.path_join(
            ctx.PROTODIR, "{}.pdf".format(test_name)
        )

        assert self.fs.is_file(proto_pdf_path)

        latex_jobname = "output"

        # Path to tex file, relative to ctx.TESTSDIR
        texfile_relpath = "{}.tex".format(test_name)

        texfile_parent_dir_relpath = os.path.dirname(texfile_relpath)
        texfile_filename = os.path.basename(texfile_relpath)
        texfile_basename = os.path.splitext(texfile_filename)[0]

        # Certain LaTeX versions have problems with build directory paths containing '[' and ']' characters
        # when going through MSYS->Windows path substitution
        texfile_basename_subst = (
            texfile_basename.replace("]", "").replace("[", "~").replace(",", "_")
            if re.search(r"\[.*\]", texfile_basename)
            else texfile_basename
        )

        texfile_parent_dir_path = self.path_util.path_join(
            ctx.TESTSDIR, texfile_parent_dir_relpath
        )
        assert self.fs.is_directory(texfile_parent_dir_path)
        assert self.fs.is_file(
            self.path_util.path_join(texfile_parent_dir_path, texfile_filename)
        )

        latex_out_dir = self.path_util.path_join(
            ctx.BUILDDIR, texfile_parent_dir_relpath, texfile_basename
        )
        latex_build_dir = self.path_util.path_join(
            ctx.BUILDDIR, texfile_parent_dir_relpath, texfile_basename_subst
        )

        async with ctx.make_task_semaphore:
            self.fs.force_remove_tree(latex_out_dir)

            self.fs.force_remove_tree(latex_build_dir)
            self.fs.mkdirp(latex_build_dir)

            self.fs.mkdirp(os.path.dirname(test_pdf_path))
            self.fs.force_remove_file(test_pdf_path)

            texfile_parent_dir_relative_to_base_dir = self.path_util.path_relpath(
                texfile_parent_dir_path, ctx.TEST_BASE_DIR
            )
            latex_build_dir_relative_to_base_dir = self.path_util.path_relpath(
                latex_build_dir, ctx.TEST_BASE_DIR
            )

            try:
                returncode, stdout, stderr = (
                    await self.latex_doc_buildtool.build_latex_document_async(
                        base_dir=ctx.TEST_BASE_DIR,
                        texfile_parent_dir_subpath=texfile_parent_dir_relative_to_base_dir,
                        texfile_filename=texfile_filename,
                        latex_build_dir_subpath=latex_build_dir_relative_to_base_dir,
                        latex_jobname=latex_jobname,
                        timeout=ctx.latex_build_timeout,
                    )
                )
            except asyncio.CancelledError:
                raise
            except asyncpopen.AsyncPopenTimeoutError as err:
                return TestResult(
                    test_name,
                    False,
                    build_timed_out=True,
                    build_returncode=err.returncode,
                    build_stdout=err.stdout,
                    build_stderr=err.stderr,
                )
            except:
                exc_info = cast(
                    tuple[Type[BaseException], BaseException, TracebackType],
                    sys.exc_info(),
                )

                return TestResult(test_name, False, exc_info=exc_info)
            finally:
                self.fs.move_directory(latex_build_dir, latex_out_dir)

            if returncode != 0:
                return TestResult(
                    test_name,
                    False,
                    build_returncode=returncode,
                    build_stdout=stdout,
                    build_stderr=stderr,
                )

            latex_build_outdir_pdf_path = self.path_util.path_join(
                latex_out_dir, "{}.pdf".format(latex_jobname)
            )

            # If we got here, then build was successful. Move PDF into pdf directory, and remove latex output directory.
            self.fs.move_file(latex_build_outdir_pdf_path, test_pdf_path)
            self.fs.force_remove_tree(latex_out_dir)

        try:
            _, failed_pages = await test_pdf_pair_async(
                ctx,
                test_name,
                test_pdf_path=test_pdf_path,
                proto_pdf_path=proto_pdf_path,
            )
        except:
            exc_info = cast(
                tuple[Type[BaseException], BaseException, TracebackType], sys.exc_info()
            )

            return TestResult(test_name, True, exc_info=exc_info)

        if not failed_pages:
            self.fs.remove_file(test_pdf_path)

        return TestResult(test_name, True, failed_pages=failed_pages)


if TYPE_CHECKING:
    _: type[ITestRunContext] = TestEngineContext  # type: ignore[no-redef]
    _: type[ITestEngine] = TestEngine  # type: ignore[no-redef]
