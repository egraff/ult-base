from typing import Sequence, TYPE_CHECKING

from .coreabc import ITestReporter
from .testresult import TestResult


class AggregateReporter:
    """Test reporter that delegates reporting to an ordered collection of
    other test reporters.
    """

    def __init__(self, reporters: Sequence[ITestReporter]) -> None:
        self.reporters = tuple(reporters)

    async def report_warmup_compile_started_async(self) -> None:
        """Report that the warmup compile step has started."""

        for reporter in self.reporters:
            await reporter.report_warmup_compile_started_async()

    async def report_warmup_compile_progress_async(self, test_name: str) -> None:
        """Report that the warmup compile step has finished processing the
        specified test.
        """

        for reporter in self.reporters:
            await reporter.report_warmup_compile_progress_async(test_name)

    async def report_warmup_compile_ended_async(self) -> None:
        """Report that the warmup compile step has ended."""

        for reporter in self.reporters:
            await reporter.report_warmup_compile_ended_async()

    async def report_test_run_started_async(self) -> None:
        """Report that the test run has started."""

        for reporter in self.reporters:
            await reporter.report_test_run_started_async()

    async def report_test_result_async(
        self, test_name: str, test_passed: bool, test_result: TestResult
    ) -> None:
        """Report the result of a single test case after having been run."""

        for reporter in self.reporters:
            await reporter.report_test_result_async(test_name, test_passed, test_result)

    async def report_test_run_result_async(self) -> None:
        """Report the result of the overall test run. The reporter is expected
        to aggregate the information it has received about the result from
        each individual test case.
        """

        for reporter in self.reporters:
            await reporter.report_test_run_result_async()


if TYPE_CHECKING:
    _: type[ITestReporter] = AggregateReporter
