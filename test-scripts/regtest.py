import argparse
import asyncio
import contextlib
import enum
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import traceback
from types import TracebackType
from typing import Any, Awaitable, Callable, List, NamedTuple, Optional, Protocol, Tuple, Type

import asynclib
from testutil import compare_pngs_async, get_png_size_async, PdfFile, mkdirp


class debug(enum.StrEnum):
    INFO = "\\033[1;34m"
    DEBUG = "\\033[0;32m"
    WARNING = "\\033[1;33m"
    NORMAL = "\\033[0m"
    BOLD = "\\033[1m"
    UNDERLINE = "\\033[4m"
    WHITE = "\\033[1;37m"
    GREEN = "\\033[1;32m"
    YELLOW = "\\033[1;33m"
    BLUE = "\\033[1;34m"
    ERROR = "\\033[1;31m"


dlvl = [
    debug.INFO,
    debug.DEBUG,
    debug.WARNING,
    debug.NORMAL,
    debug.BOLD,
    debug.UNDERLINE,
    debug.WHITE,
    debug.GREEN,
    debug.YELLOW,
    debug.BLUE,
    debug.ERROR,
]


class PathUtil(Protocol):
    def path_join(self, path: str, *paths: str) -> str:
      """Join one or more path segments."""

    def path_relpath(self, path: str, start: str = ...) -> str:
      """Return a relative filepath to path either from the current directory
      or from an optional start directory.
      """


class SystemPathUtil:
    def _normalize_path_separators(self, path: str) -> str:
        return path.replace("\\", "/")

    def path_join(self, path: str, *paths: str) -> str:
        return self._normalize_path_separators(os.path.join(path, *paths))

    def path_relpath(self, path: str, start: str = os.curdir) -> str:
        return self._normalize_path_separators(os.path.relpath(path, start))


class TestConfig(NamedTuple):
    test_base_dir: str
    proto_dir: str
    num_concurrent_processes: int = 8
    num_dots_per_line: int = 80
    run_warmup_compile_before_tests: bool = False


class TestRunContext:
    def __init__(
        self,
        config: TestConfig,
        path_util: PathUtil,
        debug_level=debug.INFO,
    ):
        self.config = config
        self.path_util = path_util

        test_base_dir = path_util.path_relpath(os.path.realpath(config.test_base_dir))
        assert os.path.isdir(test_base_dir)

        self.TEST_BASE_DIR = test_base_dir
        self.BUILDDIR = path_util.path_join(test_base_dir, ".build")
        self.TESTSDIR = path_util.path_join(test_base_dir, "tests")
        self.PDFSDIR = path_util.path_join(test_base_dir, "pdfs")
        self.PROTODIR = path_util.path_join(test_base_dir, proto_dir)
        self.TMPDIR = path_util.path_join(test_base_dir, "tmp")
        self.DIFFDIR = path_util.path_join(test_base_dir, "diffs")

        self.NUM_DOTS_PER_LINE = config.num_dots_per_line

        self.DEBUGLEVEL = debug_level

        self.run_warmup_compile_before_tests = config.run_warmup_compile_before_tests

        self.echo_lock = threading.Lock()
        self.make_task_semaphore = asyncio.BoundedSemaphore(1)
        self.process_pool_semaphore = asyncio.BoundedSemaphore(num_concurrent_processes)

        self.latex_build_timeout = 3 * 60


class TestResult:
    def __init__(
        self,
        test_name: str,
        build_succeeded: bool,
        build_timed_out: bool = False,
        exc_info: Optional[
            Tuple[Type[BaseException], BaseException, TracebackType]
        ] = None,
        build_returncode: int = 0,
        build_stdout: Optional[List[str]] = None,
        build_stderr: Optional[List[str]] = None,
        failed_pages: Optional[List[int]] = None,
    ):
        self.test_name = test_name
        self.build_succeeded = build_succeeded
        self.build_timed_out = build_timed_out
        self.exc_info = exc_info
        self.build_returncode = build_returncode
        self.build_stdout = build_stdout or []
        self.build_stderr = build_stderr or []
        self.failed_pages = failed_pages or []


async def test_pdf_page_pair_async(
    ctx: TestRunContext,
    test_pdf_obj: PdfFile,
    proto_pdf_obj: PdfFile,
    page_num: int,
    test_name: str,
) -> Awaitable[Tuple[int, bool]]:
    path_util = ctx.path_util

    png_relpath = "{}_{}.png".format(test_name, page_num)
    test_png_page_path = path_util.path_join(ctx.TMPDIR, "tests", png_relpath)
    proto_png_page_path = path_util.path_join(ctx.TMPDIR, "proto", png_relpath)
    diff_path = path_util.path_join(ctx.DIFFDIR, png_relpath)

    mkdirp(os.path.dirname(test_png_page_path))
    mkdirp(os.path.dirname(proto_png_page_path))
    mkdirp(os.path.dirname(diff_path))

    # Start processes for generating PNGs
    async with ctx.process_pool_semaphore:
        test_pdf_task = asyncio.ensure_future(
            test_pdf_obj.get_png_for_page_async(page_num, test_png_page_path)
        )
        proto_pdf_task = asyncio.ensure_future(
            proto_pdf_obj.get_png_for_page_async(page_num, proto_png_page_path)
        )

        done_futures, pending_futures = await asyncio.wait(
            [test_pdf_task, proto_pdf_task]
        )
        assert len(pending_futures) == 0

        gen_test_png_future, gen_proto_png_future = done_futures

        try:
            gen_test_png_returncode, _stdout, _stderr = await gen_test_png_future
            gen_proto_png_returncode, _stdout, _stderr = await gen_proto_png_future
        except:
            # Observe all exceptions to suppress "Task exception was never retrieved" error
            # (we are only interested in the first exception)
            _ = [x.exception() for x in done_futures]

            # Re-raise just the first exception
            raise

        assert gen_test_png_returncode == 0, "Failed to generate PNG {}".format(
            test_png_page_path
        )
        assert gen_proto_png_returncode == 0, "Failed to generate PNG {}".format(
            proto_png_page_path
        )

        # FIXME: should probably have chained each png task to each png size task, but getting the image sizes should be quick...
        test_png_size = await get_png_size_async(test_png_page_path)
        proto_png_size = await get_png_size_async(proto_png_page_path)

        if test_png_size != proto_png_size:
            return page_num, False

        ae_diff = await compare_pngs_async(
            test_png_page_path, proto_png_page_path, diff_path
        )
        pngs_are_equal = ae_diff == 0

        if pngs_are_equal:
            os.remove(test_png_page_path)
            os.remove(proto_png_page_path)
            os.remove(diff_path)

    return (page_num, pngs_are_equal)


# Use file name of PDF to determine which pages we want to test
def determine_list_of_pages_to_test(pdf_obj: PdfFile) -> List[int]:
    num_pages = pdf_obj.num_physical_pages
    basename = os.path.basename(pdf_obj.path)
    noext = os.path.splitext(basename)[0]

    # search for a range in filename ( denoted with [ ] ) and save only the range
    textrange = re.search(r"\[.*\]", noext)
    if textrange is not None:
        # remove brackets and commas
        textrange = re.sub(r"([\[\]])", r"", textrange.group()).replace(r",", " ")
        page_list = []

        # make list and translate hyphen into a sequence, e.g 3-6 -> "3 4 5 6"
        for num in textrange.split(" "):
            if "-" in num:
                numrange = num.split("-")
                assert len(numrange) == 2

                numrange = range(int(numrange[0]), int(numrange[1]) + 1)
                page_list.extend(numrange)
            else:
                page_list.append(int(num))

        page_list = sorted(set(page_list))

        for page_num in page_list:
            assert page_num <= num_pages, f"{page_num} (from '{basename}' -> {page_list}) not <= {num_pages}"
    else:
        page_list = list(range(1, num_pages + 1))

    return page_list


async def test_pdf_pair_async(
    ctx: TestRunContext, test_name: str, test_pdf_path: str, proto_pdf_path: str
) -> Awaitable[Tuple[str, List[int]]]:
    async with ctx.process_pool_semaphore:
        test_pdf_obj = await PdfFile.create(test_pdf_path)
        proto_pdf_obj = await PdfFile.create(proto_pdf_path)

    test_page_list = determine_list_of_pages_to_test(test_pdf_obj)
    proto_page_list = determine_list_of_pages_to_test(proto_pdf_obj)

    page_list = set(test_page_list + proto_page_list)

    failed_pages = []

    test_tasks = []
    for page_num in page_list:
        if page_num not in test_page_list or page_num not in proto_page_list:
            failed_pages.append(page_num)
            continue

        task = asyncio.ensure_future(
            test_pdf_page_pair_async(
                ctx, test_pdf_obj, proto_pdf_obj, page_num, test_name
            )
        )
        test_tasks.append(task)

    done_futures, pending_futures = await asyncio.wait(test_tasks)
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
    return (test_name, failed_pages)


async def make_test_tex_file_async(
    ctx: TestRunContext,
    texfile_dir: str,
    texfile_filename: str,
    latex_output_dir: str,
    latex_jobname: str,
) -> Awaitable[Tuple[int, List[str], List[str]]]:
    cmd = [
        "make",
        "-C",
        ctx.TEST_BASE_DIR,
        "--no-print-directory",
        "_file",
        "LATEXMK=latexmk",
        "PDFLATEX=pdflatex",
        "MAKEGLOSSARIES=makeglossaries",
        "TEXFILE_DIR={}".format(texfile_dir),
        "TEXFILE_FILENAME={}".format(texfile_filename),
        "LATEX_OUTPUT_DIR={}".format(latex_output_dir),
        "LATEX_JOBNAME={}".format(latex_jobname),
    ]
    return await asynclib.popen_async(
        cmd, timeout=ctx.latex_build_timeout, raise_exception_on_timeout=True
    )


async def run_test_async(ctx: TestRunContext, test_name: str) -> Awaitable[TestResult]:
    path_util = ctx.path_util

    test_pdf_path = path_util.path_join(ctx.PDFSDIR, "{}.pdf".format(test_name))
    proto_pdf_path = path_util.path_join(ctx.PROTODIR, "{}.pdf".format(test_name))

    latex_jobname = "output"

    # Path to tex file, relative to ctx.TESTSDIR
    texfile_testddir_relpath = "{}.tex".format(test_name)

    texfile_basename = os.path.splitext(os.path.basename(texfile_testddir_relpath))[0]

    # Certain LaTeX versions have problems with build directory paths containing '[' and ']' characters
    # when going through MSYS->Windows path substitution
    texfile_basename_subst = (
        texfile_basename.replace("]", "").replace("[", "~").replace(",", "_")
        if re.search(r"\[.*\]", texfile_basename)
        else texfile_basename
    )

    texfile_dirname = os.path.dirname(texfile_testddir_relpath)
    texfile_dirpath = path_util.path_join(ctx.TESTSDIR, texfile_dirname)

    texfile_filename = "{}.tex".format(texfile_basename)
    latex_build_outdir = path_util.path_join(ctx.BUILDDIR, texfile_dirname, texfile_basename)
    latex_build_outdir_subst = path_util.path_join(ctx.BUILDDIR, texfile_dirname, texfile_basename_subst)

    async with ctx.make_task_semaphore:
        shutil.rmtree(latex_build_outdir, ignore_errors=True)
        shutil.rmtree(latex_build_outdir_subst, ignore_errors=True)
        mkdirp(latex_build_outdir_subst)
        mkdirp(os.path.dirname(test_pdf_path))

        with contextlib.suppress(FileNotFoundError):
            os.remove(test_pdf_path)

        try:
            returncode, stdout, stderr = await make_test_tex_file_async(
                ctx,
                texfile_dir=path_util.path_relpath(texfile_dirpath, ctx.TEST_BASE_DIR),
                texfile_filename=texfile_filename,
                latex_output_dir=path_util.path_relpath(latex_build_outdir_subst, texfile_dirpath),
                latex_jobname=latex_jobname,
            )
        except asynclib.AsyncPopenTimeoutError as err:
            shutil.move(latex_build_outdir_subst, latex_build_outdir)
            return TestResult(
                test_name,
                False,
                build_timed_out=True,
                build_returncode=err.returncode,
                build_stdout=err.stdout,
                build_stderr=err.stderr,
            )
        except:
            shutil.move(latex_build_outdir_subst, latex_build_outdir)
            return TestResult(test_name, False, exc_info=sys.exc_info())

        shutil.move(latex_build_outdir_subst, latex_build_outdir)

        if returncode != 0:
            return TestResult(
                test_name,
                False,
                build_returncode=returncode,
                build_stdout=stdout,
                build_stderr=stderr,
            )

        latex_build_outdir_pdf_path = path_util.path_join(
            latex_build_outdir, "{}.pdf".format(latex_jobname)
        )

        # If we got here, then build was successful. Move PDF into pdf directory, and remove latex output directory.
        shutil.move(latex_build_outdir_pdf_path, test_pdf_path)
        shutil.rmtree(latex_build_outdir, ignore_errors=True)

    try:
        _, failed_pages = await test_pdf_pair_async(
            ctx,
            test_name,
            test_pdf_path=test_pdf_path,
            proto_pdf_path=proto_pdf_path,
        )
        return TestResult(test_name, True, failed_pages=failed_pages)
    except:
        return TestResult(test_name, True, exc_info=sys.exc_info())


class TestRunner:
    def __init__(self, config: TestConfig):
        self.test_result_lock = asyncio.Lock()
        self.num_tests_completed = 0
        self.failed_tests = []
        self.tasks = []
        self.ctx = TestRunContext(config)

    def echo_raw(self, echo_str):
        with self.ctx.echo_lock:
            subprocess.Popen(
                [
                    "sh",
                    "-c",
                    'printf "{}"'.format(echo_str),
                ]
            ).wait()

    def colorfmt(self, *string):
        color = ""
        if string[0] in dlvl:
            if dlvl.index(string[0]) < dlvl.index(self.ctx.DEBUGLEVEL):
                return

            color = string[0]
            string = string[1:]

        echo_str = " ".join(str(x) for x in string)
        encoded_echo_str = (
            echo_str.encode("unicode_escape").decode("utf-8").replace('"', r"\"")
        )

        if sys.platform == "win32":
            encoded_echo_str = encoded_echo_str.replace("\\", r"\\\\").replace(
                '\\"', '"'
            )

        return (color + encoded_echo_str + "\\033[0m")

    def echo(self, *string):
        self.echo_raw(self.colorfmt(*string))

    async def _run_test(self, test_name):
        test_result = await run_test_async(self.ctx, test_name)
        test_passed = (
            test_result.build_succeeded
            and (test_result.exc_info is None)
            and (len(test_result.failed_pages) == 0)
        )

        async with self.test_result_lock:
            if self.num_tests_completed % self.ctx.NUM_DOTS_PER_LINE == 0:
                self.echo(debug.BOLD, "\n")

            self.num_tests_completed += 1

            if test_passed:
                self.echo(debug.GREEN, ".")
            else:
                if test_result.build_timed_out:
                    self.echo(debug.ERROR, "T")
                elif test_result.exc_info:
                    self.echo(debug.ERROR, "E")
                elif not test_result.build_succeeded:
                    self.echo(debug.ERROR, "B")
                else:
                    self.echo(debug.ERROR, "F")

                self.failed_tests.append(test_result)

    async def run(self, test_names) -> int:
        if self.ctx.run_warmup_compile_before_tests:
            await self._run_warmup_compile(test_names)

        return await self._run_tests(test_names)

    async def _run_warmup_compile(self, test_names):
        path_util = self.ctx.path_util

        self.echo(debug.BOLD, "Running warmup compile step...\n")
        for i, test_name in enumerate(test_names):
            latex_jobname = "output"

            # Path to tex file, relative to ctx.TESTSDIR
            texfile_testddir_relpath = "{}.tex".format(test_name)

            texfile_basename = os.path.splitext(os.path.basename(texfile_testddir_relpath))[0]

            # Certain LaTeX versions have problems with build directory paths containing '[' and ']' characters
            # when going through MSYS->Windows path substitution
            texfile_basename_subst = (
                texfile_basename.replace("]", "").replace("[", "~").replace(",", "_")
                if re.search(r"\[.*\]", texfile_basename)
                else texfile_basename
            )

            texfile_dirname = os.path.dirname(texfile_testddir_relpath)
            texfile_dirpath = path_util.path_join(self.ctx.TESTSDIR, texfile_dirname)

            texfile_filename = "{}.tex".format(texfile_basename)
            latex_build_outdir = path_util.path_join(self.ctx.BUILDDIR, texfile_dirname, texfile_basename_subst)

            shutil.rmtree(latex_build_outdir, ignore_errors=True)
            mkdirp(latex_build_outdir)

            for _ in range(2):
                try:
                    returncode, stdout, stderr = await make_test_tex_file_async(
                        self.ctx,
                        texfile_dir=path_util.path_relpath(texfile_dirpath, self.ctx.TEST_BASE_DIR),
                        texfile_filename=texfile_filename,
                        latex_output_dir=path_util.path_relpath(latex_build_outdir, texfile_dirpath),
                        latex_jobname=latex_jobname,
                    )
                except:
                    pass

            shutil.rmtree(latex_build_outdir, ignore_errors=True)

            if i % self.ctx.NUM_DOTS_PER_LINE == 0:
                self.echo(debug.BOLD, "\n")

            self.echo(debug.NORMAL, ".")

        self.echo(debug.BOLD, "\n\nWarmup compile step done!\n\n")

    async def _run_tests(self, test_names) -> int:
        path_util = self.ctx.path_util

        tasks = []
        for test_name in test_names:
            task = asyncio.ensure_future(self._run_test(test_name))
            tasks.append(task)

        done_futures, pending_futures = await asyncio.wait(tasks)
        assert len(pending_futures) == 0

        for future in done_futures:
            # Await to allow a potential exception to propagate
            try:
                await future
            except:
                # Observe all exceptions to suppress "Task exception was never retrieved" error
                # (we are only interested in the first exception)
                _ = [x.exception() for x in done_futures]

                # Re-raise just the first exception
                raise

        result_map = {}

        async with self.test_result_lock:
            with open(
                path_util.path_join(self.ctx.TEST_BASE_DIR, "test_result.json"),
                "w",
                encoding="utf8",
            ) as fp:
                result_map["num_tests"] = self.num_tests_completed
                result_map["failed_tests"] = []
                self.echo(
                    debug.BOLD, "\n\n\nRan %s tests, " % (self.num_tests_completed,)
                )

                if len(self.failed_tests) == 0:
                    self.echo(debug.GREEN, "all succeeded!\n\n")
                    json.dump(result_map, fp)
                    return 0

                self.echo(debug.ERROR, "%s failed" % (len(self.failed_tests),))
                self.echo(debug.BOLD, ".\n\nError summary:\n\n")

                for test_result in self.failed_tests:
                    # Buffer output in StringIO, to limit the number of echo
                    # processes being spawned within a short time period
                    #
                    # This is done to prevent errors written to stderr looking like this:
                    #   Exception ignored when trying to write to the signal wakeup fd:
                    #   BlockingIOError: [Errno 11] Resource temporarily unavailable
                    echo_out = io.StringIO()
                    echo = lambda *args: echo_out.write(self.colorfmt(*args))

                    failed_test_map = {}
                    failed_test_map["test_name"] = test_result.test_name
                    failed_test_map["build_succeeded"] = test_result.build_succeeded
                    failed_test_map["build_timed_out"] = test_result.build_timed_out
                    failed_test_map["exception"] = (
                        False if test_result.exc_info is None else True
                    )

                    echo(debug.BOLD, "  %s\n" % (test_result.test_name,))

                    if test_result.build_timed_out:
                        failed_test_map["proc"] = {}
                        failed_test_map["proc"][
                            "returncode"
                        ] = test_result.build_returncode
                        failed_test_map["proc"]["stdout"] = []
                        failed_test_map["proc"]["stderr"] = []

                        echo(debug.ERROR, "    Build timed out!\n")

                        echo(debug.ERROR, "    stdout output:\n")
                        for line in test_result.build_stdout:
                            line = line.rstrip(b"\n").decode("utf-8")
                            failed_test_map["proc"]["stdout"].append(line)
                            echo(debug.NORMAL, "      %s\n" % (line,))

                        echo(debug.ERROR, "\n    stderr output:\n")
                        for line in test_result.build_stderr:
                            line = line.rstrip(b"\n").decode("utf-8")
                            failed_test_map["proc"]["stderr"].append(line)
                            echo(debug.NORMAL, "      %s\n" % (line,))

                        latex_log_file = path_util.path_join(
                            self.ctx.BUILDDIR, test_result.test_name, "output.log"
                        )
                        if os.path.exists(latex_log_file):
                            latex_log_file_relpath = path_util.path_relpath(
                                latex_log_file, self.ctx.TEST_BASE_DIR
                            )
                            failed_test_map["log_file"] = latex_log_file_relpath
                            echo(
                                debug.BOLD,
                                "\n    see {} for more info.\n\n".format(
                                    latex_log_file_relpath
                                ),
                            )
                        else:
                            echo(debug.BOLD, "\n\n")
                    elif test_result.exc_info is not None:
                        failed_test_map["exc_info"] = {}
                        failed_test_map["exc_info"]["type"] = str(
                            test_result.exc_info[0]
                        )
                        failed_test_map["exc_info"]["value"] = str(
                            test_result.exc_info[1]
                        )
                        failed_test_map["exc_info"]["traceback"] = []

                        echo(
                            debug.ERROR,
                            "    Got exception %s: %s\n"
                            % (test_result.exc_info[0], test_result.exc_info[1]),
                        )
                        echo(debug.ERROR, "    Traceback:\n")
                        for frame in traceback.format_tb(test_result.exc_info[2]):
                            for line in frame.split("\n"):
                                line = line.rstrip("\n")
                                failed_test_map["exc_info"]["traceback"].append(line)
                                echo(debug.NORMAL, "      %s\n" % (line,))
                    elif not test_result.build_succeeded:
                        failed_test_map["proc"] = {}
                        failed_test_map["proc"][
                            "returncode"
                        ] = test_result.build_returncode
                        failed_test_map["proc"]["stdout"] = []
                        failed_test_map["proc"]["stderr"] = []

                        echo(debug.ERROR, "    Build failed!\n")

                        echo(debug.ERROR, "    stdout output:\n")
                        for line in test_result.build_stdout:
                            line = line.rstrip(b"\n").decode("utf-8")
                            failed_test_map["proc"]["stdout"].append(line)
                            echo(debug.NORMAL, "      %s\n" % (line,))

                        echo(debug.ERROR, "\n    stderr output:\n")
                        for line in test_result.build_stderr:
                            line = line.rstrip(b"\n").decode("utf-8")
                            failed_test_map["proc"]["stderr"].append(line)
                            echo(debug.NORMAL, "      %s\n" % (line,))

                        latex_log_file = path_util.path_join(
                            self.ctx.BUILDDIR, test_result.test_name, "output.log"
                        )
                        if os.path.exists(latex_log_file):
                            latex_log_file_relpath = path_util.path_relpath(
                                latex_log_file, self.ctx.TEST_BASE_DIR
                            )
                            failed_test_map["log_file"] = latex_log_file_relpath
                            echo(
                                debug.BOLD,
                                "\n    see {} for more info.\n\n".format(
                                    latex_log_file_relpath
                                ),
                            )
                        else:
                            echo(debug.BOLD, "\n\n")
                    else:
                        failed_test_map["failed_pages"] = test_result.failed_pages
                        failed_pages_string = ", ".join(
                            str(x) for x in test_result.failed_pages
                        )

                        echo(
                            debug.ERROR,
                            "    Pages with diff: %s.\n\n" % (failed_pages_string,),
                        )

                    self.echo_raw(echo_out.getvalue())

                    result_map["failed_tests"].append(failed_test_map)

                self.echo(
                    debug.BLUE,
                    "PNGs containing diffs are available in '%s'\n\n"
                    % (self.ctx.DIFFDIR,),
                )
                json.dump(result_map, fp)
                return 1


def test_generator(path_util: PathUtil, tex_tests_root_dir: str, test_file_prefix: str = "test", test_name_filter: Callable[[str], bool] = lambda _: True):
    for dir_path, _dir_names, file_names in os.walk(tex_tests_root_dir):
        for file_name in file_names:
            # Ignore files that contain spaces
            if " " in file_name:
                continue

            if not file_name.startswith(test_file_prefix):
                continue

            if not file_name.endswith(".tex"):
                continue

            filebasename = os.path.splitext(file_name)[0]
            test_name = path_util.path_relpath(
                path_util.path_join(dir_path, filebasename), tex_tests_root_dir
            )

            if not test_name_filter(test_name):
                continue

            yield test_name


def _dirname(val) -> str:
    assert isinstance(val, str)

    if (os.path.sep in val) or ("/" in val) or (".." in val):
        raise argparse.ArgumentTypeError("should be a folder name, not a path")

    return val


def _str2bool(val: str) -> bool:
    assert isinstance(val, str)

    if val.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif val.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError(f'Boolean value expected, got {val}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "test_base_dir",
        metavar="<test base folder>",
        type=str,
        help="the base folder for the tests",
    )
    parser.add_argument(
        "--test",
        dest="test_name",
        type=str,
        default=None,
        help="the name of a specific test to run",
    )
    parser.add_argument(
        "--protodir",
        dest="proto_dir",
        type=_dirname,
        default="proto",
        help="the name of the test prototype folder",
    )
    parser.add_argument(
        "--warmup-compile",
        dest="run_warmup_compile_before_tests",
        type=_str2bool,
        default=False,
        help="whether to run a warmup compile step before executing the tests",
    )

    args = parser.parse_args()

    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.SelectorEventLoop()

    asyncio.set_event_loop(loop)

    path_util = SystemPathUtil()

    test_base_dir = args.test_base_dir
    tex_tests_root_dir = path_util.path_join(test_base_dir, "tests")

    config = TestConfig(
        test_base_dir,
        proto_dir=args.proto_dir,
        num_concurrent_processes=min(max(int(1.5 * os.cpu_count()), 2), 16),
        run_warmup_compile_before_tests=args.run_warmup_compile_before_tests,
    )
    runner = TestRunner(config)

    if args.test_name is not None:
        tests = [args.test_name]
    else:
        tests = [test_name for test_name in test_generator(path_util, tex_tests_root_dir)]

    try:
        retcode = loop.run_until_complete(runner.run(tests))
    finally:
        loop.close()

    sys.exit(retcode)
