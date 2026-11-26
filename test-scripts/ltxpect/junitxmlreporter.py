import asyncio
import os
import re
import time
import traceback
from typing import TYPE_CHECKING

import xml.etree.ElementTree as ET

from .coreabc import ITestReporter
from .testresult import TestResult

# Strip ASCII control characters disallowed in XML 1.0 (e.g. from LaTeX logs)
_INVALID_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _sanitize_xml_text(text: str) -> str:
    return _INVALID_XML_CHARS_RE.sub("", text)


class JUnitXmlReporter:
    """Writes test results in JUnit XML compatible format."""

    def __init__(self, junit_xml_path: str, suite_name: str) -> None:
        self.junit_xml_path = junit_xml_path
        self.suite_name = suite_name

        self.test_result_lock = asyncio.Lock()
        self.start_time: float | None = None
        self.results: list[tuple[str, bool, TestResult]] = []

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

        self.start_time = time.monotonic()

    async def report_test_result_async(
        self, test_name: str, test_passed: bool, test_result: TestResult
    ) -> None:
        """Report the result of a single test case after having been run."""

        async with self.test_result_lock:
            self.results.append((test_name, test_passed, test_result))

    async def report_test_run_result_async(self) -> None:
        """Report the result of the overall test run."""

        elapsed = (
            time.monotonic() - self.start_time
            if self.start_time is not None
            else 0.0
        )

        async with self.test_result_lock:
            sorted_results = sorted(self.results, key=lambda item: item[0])

            num_tests = len(sorted_results)
            num_failures = 0
            num_errors = 0

            testsuites = ET.Element("testsuites")
            testsuite = ET.SubElement(
                testsuites,
                "testsuite",
                name=self.suite_name,
                tests=str(num_tests),
                time=f"{elapsed:.3f}",
            )

            for test_name, test_passed, test_result in sorted_results:
                testcase = ET.SubElement(
                    testsuite,
                    "testcase",
                    classname=self.suite_name,
                    name=test_name,
                    file=f"tests/{test_name}.tex",
                )

                if test_passed:
                    continue

                if test_result.exc_info is not None:
                    num_errors += 1
                    exc_type, exc_val, exc_tb = test_result.exc_info
                    tb_text = "".join(
                        traceback.format_exception(exc_type, exc_val, exc_tb)
                    )
                    err_elem = ET.SubElement(
                        testcase,
                        "error",
                        type=exc_type.__name__,
                        message=_sanitize_xml_text(str(exc_val)),
                    )
                    err_elem.text = _sanitize_xml_text(tb_text)
                elif test_result.build_timed_out or not test_result.build_succeeded:
                    num_failures += 1
                    if test_result.build_timed_out:
                        failure_type = "BuildTimeout"
                        msg = "Build timed out"
                    else:
                        failure_type = "BuildFailure"
                        msg = (
                            "Build failed with return code "
                            f"{test_result.build_returncode}"
                        )

                    details: list[str] = []
                    if test_result.build_logfile:
                        details.append(f"Log file: {test_result.build_logfile}")
                    if test_result.build_stdout:
                        stdout_str = "\n".join(
                            line.rstrip(b"\n").decode("utf-8", errors="replace")
                            for line in test_result.build_stdout
                        )
                        details.append(f"stdout:\n{stdout_str}")
                    if test_result.build_stderr:
                        stderr_str = "\n".join(
                            line.rstrip(b"\n").decode("utf-8", errors="replace")
                            for line in test_result.build_stderr
                        )
                        details.append(f"stderr:\n{stderr_str}")

                    fail_elem = ET.SubElement(
                        testcase,
                        "failure",
                        type=failure_type,
                        message=_sanitize_xml_text(msg),
                    )
                    fail_elem.text = _sanitize_xml_text("\n\n".join(details))
                else:
                    num_failures += 1
                    pages_str = ", ".join(str(p) for p in test_result.failed_pages)
                    msg = f"Pages with diff: {pages_str}"
                    fail_elem = ET.SubElement(
                        testcase,
                        "failure",
                        type="ComparisonFailure",
                        message=_sanitize_xml_text(msg),
                    )
                    fail_elem.text = _sanitize_xml_text(msg)

            testsuite.set("failures", str(num_failures))
            testsuite.set("errors", str(num_errors))

        parent_dir = os.path.dirname(os.path.abspath(self.junit_xml_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        ET.indent(testsuites, space="  ")
        tree = ET.ElementTree(testsuites)
        tree.write(self.junit_xml_path, encoding="utf-8", xml_declaration=True)


if TYPE_CHECKING:
    _: type[ITestReporter] = JUnitXmlReporter
