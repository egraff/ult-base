#!/usr/bin/env python

import asyncio
import json
import os
import re
import subprocess
import sys
import threading
import traceback
from types import TracebackType
from typing import Any, Awaitable, List, Optional, Tuple, Type

import asynclib
from testutil import compare_pngs_async, get_png_size_async, PdfFile, mkdirp


class debug:
    NORMAL = "\\033[0m"
    INFO = "\\033[1;34m"
    DEBUG = "\\033[0;32m"
    WARNING = "\\033[1;33m"
    YELLOW = "\\033[1;33m"
    BLUE = "\\033[1;34m"
    ERROR = "\\033[1;31m"
    FUCK = "\\033[1;41m"
    GREEN = "\\033[1;32m"
    WHITE = "\\033[1;37m"
    BOLD = "\\033[1m"
    UNDERLINE = "\\033[4m"


dlvl = [
    debug.INFO,
    debug.DEBUG,
    debug.WARNING,
    debug.FUCK,
    debug.NORMAL,
    debug.BOLD,
    debug.UNDERLINE,
    debug.WHITE,
    debug.GREEN,
    debug.YELLOW,
    debug.BLUE,
    debug.ERROR,
]


class TestConfig:
    def __init__(self, test_dir, num_dots_per_line=80, debug_level=debug.INFO):
        test_dir = os.path.relpath(os.path.realpath(test_dir)).replace("\\", "/")
        assert os.path.isdir(test_dir)

        self.TESTDIR = test_dir
        self.PDFSDIR = os.path.join(test_dir, "pdfs").replace("\\", "/")
        self.PROTODIR = os.path.join(test_dir, "proto").replace("\\", "/")
        self.TMPDIR = os.path.join(test_dir, "tmp").replace("\\", "/")
        self.DIFFDIR = os.path.join(test_dir, "diffs").replace("\\", "/")

        self.NUM_DOTS_PER_LINE = num_dots_per_line

        self.DEBUGLEVEL = debug_level

        self.echo_lock = threading.Lock()
        self.make_task_semaphore = asyncio.BoundedSemaphore(1)
        self.process_pool_semaphore = asyncio.BoundedSemaphore(8)


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
    config: TestConfig,
    test_pdf_obj: PdfFile,
    proto_pdf_obj: PdfFile,
    page_num: int,
    test_name: str,
) -> Awaitable[Tuple[int, bool]]:
    tmp_tests_dir = "%s/tests" % (config.TMPDIR,)
    tmp_proto_dir = "%s/proto" % (config.TMPDIR,)
    diff_dir = config.DIFFDIR

    test_png_page_path = "%s/%s_%s.png" % (tmp_tests_dir, test_name, page_num)
    proto_png_page_path = "%s/%s_%s.png" % (tmp_proto_dir, test_name, page_num)
    diff_path = "%s/%s_%s.png" % (diff_dir, test_name, page_num)

    mkdirp(os.path.dirname(test_png_page_path))
    mkdirp(os.path.dirname(proto_png_page_path))
    mkdirp(os.path.dirname(diff_path))

    # Start processes for generating PNGs
    async with config.process_pool_semaphore:
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

        assert gen_test_png_returncode == 0, "Failed to generate PNG %s" % (
            test_png_page_path,
        )
        assert gen_proto_png_returncode == 0, "Failed to generate PNG %s" % (
            proto_png_page_path,
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
            assert page_num <= num_pages
    else:
        page_list = list(range(1, num_pages + 1))

    return page_list


async def test_pdf_pair_async(
    config: TestConfig, test_name: str
) -> Awaitable[Tuple[str, List[int]]]:
    test_pdf_path = "%s/%s.pdf" % (config.PDFSDIR, test_name)
    proto_pdf_path = "%s/%s.pdf" % (config.PROTODIR, test_name)

    async with config.process_pool_semaphore:
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
                config, test_pdf_obj, proto_pdf_obj, page_num, test_name
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

    # Result is on the form (testname, list of failed pages)
    return (test_name, failed_pages)


async def make_test_tex_file_async(
    config: TestConfig, test_name: str
) -> Awaitable[Tuple[int, List[str], List[str]]]:
    cmd = [
        "make",
        "-C",
        config.TESTDIR,
        "--no-print-directory",
        "_file",
        "RETAINBUILDFLD=y",
        "FILE=%s.tex" % (test_name,),
    ]
    return await asynclib.popen_async(cmd, timeout=120, raise_exception_on_timeout=True)


async def run_test_async(config: TestConfig, test_name: str) -> Awaitable[TestResult]:
    async with config.make_task_semaphore:
        try:
            returncode, stdout, stderr = await make_test_tex_file_async(
                config, test_name
            )
        except asynclib.AsyncPopenTimeoutError as err:
            return TestResult(
                test_name,
                False,
                build_timed_out=True,
                build_returncode=err.returncode,
                build_stdout=err.stdout,
                build_stderr=err.stderr,
            )
        except:
            return TestResult(test_name, False, exc_info=sys.exc_info())

    if returncode != 0:
        return TestResult(
            test_name,
            False,
            build_returncode=returncode,
            build_stdout=stdout,
            build_stderr=stderr,
        )

    try:
        _, failed_pages = await test_pdf_pair_async(config, test_name)
        return TestResult(test_name, True, failed_pages=failed_pages)
    except:
        return TestResult(test_name, True, exc_info=sys.exc_info())


class TestRunner:
    def __init__(self, config):
        self.test_result_lock = asyncio.Lock()
        self.num_tests_completed = 0
        self.failed_tests = []
        self.tasks = []
        self.config = config

    def echo(self, *string):
        color = ""
        if string[0] in dlvl:
            if dlvl.index(string[0]) < dlvl.index(self.config.DEBUGLEVEL):
                return

            color = string[0]
            string = string[1:]

        echo_str = " ".join(str(x) for x in string)
        with self.config.echo_lock:
            subprocess.Popen(
                [
                    "sh",
                    "-c",
                    'printf "{}"; printf "{}"; printf "{}"'.format(
                        color,
                        echo_str.encode("unicode_escape")
                        .decode("utf-8")
                        .replace('"', r"\""),
                        "\\033[0m",
                    ),
                ]
            ).wait()

    async def _run_test(self, test_name):
        test_result = await run_test_async(self.config, test_name)
        test_passed = (
            test_result.build_succeeded
            and (test_result.exc_info is None)
            and (len(test_result.failed_pages) == 0)
        )

        async with self.test_result_lock:
            if self.num_tests_completed % self.config.NUM_DOTS_PER_LINE == 0:
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

    async def run(self, test_names):
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
                os.path.join(self.config.TESTDIR, "test_result.json").replace(
                    "\\", "/"
                ),
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
                    failed_test_map = {}
                    failed_test_map["test_name"] = test_result.test_name
                    failed_test_map["build_succeeded"] = test_result.build_succeeded
                    failed_test_map["build_timed_out"] = test_result.build_timed_out
                    failed_test_map["exception"] = (
                        False if test_result.exc_info is None else True
                    )

                    self.echo(debug.BOLD, "  %s\n" % (test_result.test_name,))

                    if test_result.build_timed_out:
                        failed_test_map["proc"] = {}
                        failed_test_map["proc"][
                            "returncode"
                        ] = test_result.build_returncode
                        failed_test_map["proc"]["stdout"] = []
                        failed_test_map["proc"]["stderr"] = []

                        self.echo(debug.ERROR, "    Build timed out!\n")

                        self.echo(debug.ERROR, "    stdout output:\n")
                        for line in test_result.build_stdout:
                            line = line.rstrip(b"\n").decode("utf-8")
                            failed_test_map["proc"]["stdout"].append(line)
                            self.echo(debug.NORMAL, "      %s\n" % (line,))

                        self.echo(debug.ERROR, "\n    stderr output:\n")
                        for line in test_result.build_stderr:
                            line = line.rstrip(b"\n").decode("utf-8")
                            failed_test_map["proc"]["stderr"].append(line)
                            self.echo(debug.NORMAL, "      %s\n" % (line,))

                        latex_log_file = ".build/%s/output.log" % (
                            test_result.test_name,
                        )
                        if os.path.exists(latex_log_file):
                            failed_test_map["log_file"] = latex_log_file
                            self.echo(
                                debug.BOLD,
                                "\n    see %s for more info.\n\n" % (latex_log_file,),
                            )
                        else:
                            self.echo(debug.BOLD, "\n\n")
                    elif test_result.exc_info is not None:
                        failed_test_map["exc_info"] = {}
                        failed_test_map["exc_info"]["type"] = str(
                            test_result.exc_info[0]
                        )
                        failed_test_map["exc_info"]["value"] = str(
                            test_result.exc_info[1]
                        )
                        failed_test_map["exc_info"]["traceback"] = []

                        self.echo(
                            debug.ERROR,
                            "    Got exception %s: %s\n"
                            % (test_result.exc_info[0], test_result.exc_info[1]),
                        )
                        self.echo(debug.ERROR, "    Traceback:\n")
                        for frame in traceback.format_tb(test_result.exc_info[2]):
                            for line in frame.split("\n"):
                                line = line.rstrip("\n")
                                failed_test_map["exc_info"]["traceback"].append(line)
                                self.echo(debug.NORMAL, "      %s\n" % (line,))
                    elif not test_result.build_succeeded:
                        failed_test_map["proc"] = {}
                        failed_test_map["proc"][
                            "returncode"
                        ] = test_result.build_returncode
                        failed_test_map["proc"]["stdout"] = []
                        failed_test_map["proc"]["stderr"] = []

                        self.echo(debug.ERROR, "    Build failed!\n")

                        self.echo(debug.ERROR, "    stdout output:\n")
                        for line in test_result.build_stdout:
                            line = line.rstrip(b"\n").decode("utf-8")
                            failed_test_map["proc"]["stdout"].append(line)
                            self.echo(debug.NORMAL, "      %s\n" % (line,))

                        self.echo(debug.ERROR, "\n    stderr output:\n")
                        for line in test_result.build_stderr:
                            line = line.rstrip(b"\n").decode("utf-8")
                            failed_test_map["proc"]["stderr"].append(line)
                            self.echo(debug.NORMAL, "      %s\n" % (line,))

                        latex_log_file = ".build/%s/output.log" % (
                            test_result.test_name,
                        )
                        if os.path.exists(latex_log_file):
                            failed_test_map["log_file"] = latex_log_file
                            self.echo(
                                debug.BOLD,
                                "\n    see %s for more info.\n\n" % (latex_log_file,),
                            )
                        else:
                            self.echo(debug.BOLD, "\n\n")
                    else:
                        failed_test_map["failed_pages"] = test_result.failed_pages
                        failed_pages_string = ", ".join(
                            str(x) for x in test_result.failed_pages
                        )

                        self.echo(
                            debug.ERROR,
                            "    Pages with diff: %s.\n\n" % (failed_pages_string,),
                        )

                    result_map["failed_tests"].append(failed_test_map)

                self.echo(
                    debug.BLUE,
                    "PNGs containing diffs are available in '%s'\n\n"
                    % (self.config.DIFFDIR,),
                )
                json.dump(result_map, fp)
                return 1


def test_generator(tex_tests_root_dir: str, test_file_prefix="test"):
    for dir_path, dir_names, file_names in os.walk(tex_tests_root_dir):
        for file_name in file_names:
            # Ignore files that contain spaces
            if " " in file_name:
                continue

            if not file_name.startswith(test_file_prefix):
                continue

            if not file_name.endswith(".tex"):
                continue

            filebasename = os.path.splitext(file_name)[0]
            test_name = os.path.relpath(
                os.path.join(dir_path, filebasename), tex_tests_root_dir
            ).replace("\\", "/")

            yield test_name


if __name__ == "__main__":
    if len(sys.argv) not in [2, 3]:
        print("Usage: %s <test base folder> [<test name>]" % sys.argv[0])
        sys.exit(1)

    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.SelectorEventLoop()

    asyncio.set_event_loop(loop)

    test_dir = sys.argv[1]
    tex_tests_root_dir = os.path.join(test_dir, "tests").replace("\\", "/")

    config = TestConfig(test_dir)
    runner = TestRunner(config)

    if len(sys.argv) == 3:
        test_name = sys.argv[2]
        tests = [test_name]
    else:
        tests = [tup for tup in test_generator(tex_tests_root_dir)]

    try:
        retcode = loop.run_until_complete(runner.run(tests))
    finally:
        loop.close()

    sys.exit(retcode)
