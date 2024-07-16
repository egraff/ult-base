import asyncio
import json
import traceback
from typing import Any, TYPE_CHECKING

from .coreabc import ITestReporter
from .testresult import TestResult


class TestResultsJsonReporter:
    """Writes test results to a JSON file."""

    def __init__(self, test_result_json_path: str) -> None:
        self.test_result_json_path = test_result_json_path

        self.test_result_lock = asyncio.Lock()
        self.num_tests_completed: int = 0
        self.failed_tests: list[TestResult] = []

    async def report_warmup_compile_started_async(self) -> None:
        """Report that the warmup compile step has started."""

    async def report_warmup_compile_progress_async(self, test_name: str) -> None:
        """Report that the warmup compile step has finished processing the
        specified test.
        """

    async def report_warmup_compile_ended_async(self) -> None:
        """Report that the warmup compile step has ended."""

    async def report_test_run_started_async(self) -> None:
        """Report that the test run has started."""

    async def report_test_result_async(
        self, test_name: str, test_passed: bool, test_result: TestResult
    ) -> None:
        """Report the result of a single test case after having been run."""

        _ = test_name

        async with self.test_result_lock:
            self.num_tests_completed += 1

            if not test_passed:
                self.failed_tests.append(test_result)

    async def report_test_run_result_async(self) -> None:
        """Report the result of the overall test run. The reporter is expected
        to aggregate the information it has received about the result from
        each individual test case.
        """

        result_map: dict[str, Any] = {}
        async with self.test_result_lock:
            result_map["num_tests"] = self.num_tests_completed

            failed_tests_list: list[dict[str, Any]] = []
            for test_result in self.failed_tests:
                failed_test_map: dict[str, Any] = {}
                failed_test_map["test_name"] = test_result.test_name
                failed_test_map["build_succeeded"] = test_result.build_succeeded
                failed_test_map["build_timed_out"] = test_result.build_timed_out
                failed_test_map["exception"] = (
                    False if test_result.exc_info is None else True
                )

                if test_result.exc_info is not None:
                    exc_type, exc_val, exc_tb = test_result.exc_info

                    failed_test_map["exc_info"] = {}
                    failed_test_map["exc_info"]["type"] = str(exc_type)
                    failed_test_map["exc_info"]["value"] = str(exc_val)

                    failed_test_map["exc_info"]["traceback"] = [
                        line.rstrip("\n")
                        for frame in traceback.format_tb(exc_tb)
                        for line in frame.split("\n")
                    ]
                elif test_result.build_timed_out or not test_result.build_succeeded:
                    failed_test_map["proc"] = {}
                    failed_test_map["proc"]["returncode"] = test_result.build_returncode

                    failed_test_map["proc"]["stdout"] = [
                        line.rstrip(b"\n").decode("utf-8")
                        for line in test_result.build_stdout
                    ]

                    failed_test_map["proc"]["stderr"] = [
                        line.rstrip(b"\n").decode("utf-8")
                        for line in test_result.build_stderr
                    ]

                    if test_result.build_logfile:
                        failed_test_map["log_file"] = test_result.build_logfile
                else:
                    failed_test_map["failed_pages"] = test_result.failed_pages

                failed_tests_list.append(failed_test_map)

            result_map["failed_tests"] = failed_tests_list

        with open(
            self.test_result_json_path,
            "w",
            encoding="utf8",
        ) as fp:
            json.dump(result_map, fp)


if TYPE_CHECKING:
    _: type[ITestReporter] = TestResultsJsonReporter
