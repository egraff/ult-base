import asyncio
import io
import subprocess
import sys
import threading
import traceback
from typing import TYPE_CHECKING

from .coreabc import ITestReporter
from .testresult import TestResult


class debug:
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


class ColorConsoleReporter:
    def __init__(self) -> None:
        self.test_result_lock = asyncio.Lock()
        self.num_warmup_tests_completed = 0
        self.num_tests_completed = 0
        self.echo_lock = threading.Lock()
        self.debug_level = debug.INFO
        self.NUM_DOTS_PER_LINE = 80
        self.failed_tests: list[TestResult] = []

    async def report_warmup_compile_started_async(self) -> None:
        """Report that the warmup compile step has started."""

        self.echo(debug.BOLD, "Running warmup compile step...\n")

    async def report_warmup_compile_progress_async(self, test_name: str) -> None:
        """Report that the warmup compile step has finished processing the
        specified test.
        """

        async with self.test_result_lock:
            if self.num_warmup_tests_completed % self.NUM_DOTS_PER_LINE == 0:
                self.echo(debug.BOLD, "\n")

            self.num_warmup_tests_completed += 1

            self.echo(debug.NORMAL, ".")

    async def report_warmup_compile_ended_async(self) -> None:
        """Report that the warmup compile step has ended."""

        self.echo(debug.BOLD, "\n\nWarmup compile step done!\n\n")

    async def report_test_run_started_async(self) -> None:
        """Report that the test run has started."""

    async def report_test_result_async(
        self, test_name: str, test_passed: bool, test_result: TestResult
    ) -> None:
        """Report the result of a single test case after having been run."""

        async with self.test_result_lock:
            if self.num_tests_completed % self.NUM_DOTS_PER_LINE == 0:
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

    async def report_test_run_result_async(self) -> None:
        """Report the result of the overall test run. The reporter is expected
        to aggregate the information it has received about the result from
        each individual test case.
        """

        async with self.test_result_lock:
            self.echo(debug.BOLD, "\n\n\nRan %s tests, " % (self.num_tests_completed,))

            if len(self.failed_tests) == 0:
                self.echo(debug.GREEN, "all succeeded!\n\n")
                return

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

                echo(debug.BOLD, "  %s\n" % (test_result.test_name,))

                if test_result.exc_info is not None:
                    exc_type, exc_val, exc_tb = test_result.exc_info

                    echo(
                        debug.ERROR,
                        "    Got exception %s: %s\n" % (exc_type, exc_val),
                    )
                    echo(debug.ERROR, "    Traceback:\n")
                    for tb_frame in traceback.format_tb(exc_tb):
                        for tb_line in tb_frame.split("\n"):
                            tb_line = tb_line.rstrip("\n")
                            echo(debug.NORMAL, "      %s\n" % (tb_line,))
                elif test_result.build_timed_out or not test_result.build_succeeded:
                    if test_result.build_timed_out:
                        echo(debug.ERROR, "    Build timed out!\n")
                    else:
                        echo(debug.ERROR, "    Build failed!\n")

                    echo(debug.ERROR, "    stdout output:\n")
                    for bline in test_result.build_stdout:
                        line = bline.rstrip(b"\n").decode("utf-8")
                        echo(debug.NORMAL, "      %s\n" % (line,))

                    echo(debug.ERROR, "\n    stderr output:\n")
                    for bline in test_result.build_stderr:
                        line = bline.rstrip(b"\n").decode("utf-8")
                        echo(debug.NORMAL, "      %s\n" % (line,))

                    if test_result.build_logfile:
                        echo(
                            debug.BOLD,
                            "\n    see {} for more info.\n\n".format(
                                test_result.build_logfile
                            ),
                        )

    def echo_raw(self, echo_str):
        with self.echo_lock:
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
            if dlvl.index(string[0]) < dlvl.index(self.debug_level):
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

        return color + encoded_echo_str + "\\033[0m"

    def echo(self, *string):
        self.echo_raw(self.colorfmt(*string))


if TYPE_CHECKING:
    _: type[ITestReporter] = ColorConsoleReporter
