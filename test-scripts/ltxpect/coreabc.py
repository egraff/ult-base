from collections.abc import Sequence
from typing import Awaitable, Protocol, runtime_checkable

from .testresult import TestResult


@runtime_checkable
class IExternalProgramLocator(Protocol):
    def find_program(self, appname: str, app_cmd_candidates: list[str]) -> str: ...


@runtime_checkable
class IPathUtil(Protocol):
    def path_join(self, path: str, *paths: str) -> str:
        """Join one or more path segments."""

    def path_relpath(self, path: str, start: str = ...) -> str:
        """Return a relative filepath to path either from the current directory
        or from an optional start directory.
        """


@runtime_checkable
class IFileSystem(Protocol):
    def resolve_path(self, path: str) -> str: ...

    def is_file(self, path: str) -> bool: ...

    def is_directory(self, path: str) -> bool: ...

    def mkdirp(self, dirpath: str) -> None: ...

    def remove_file(self, filepath: str) -> None: ...

    def force_remove_file(self, filepath: str) -> None: ...

    def force_remove_tree(self, dirpath: str) -> None: ...

    def move_directory(self, oldpath: str, newpath: str) -> None: ...

    def move_file(self, oldpath: str, newpath: str) -> None: ...


@runtime_checkable
class ITestRunContext(Protocol):
    """Context object that is used by a test engine to represent a distinct
    test run.
    """


@runtime_checkable
class ITestEngine(Protocol):
    """Responsible for execution of test logic."""

    def create_test_run_context(self) -> ITestRunContext:
        """Create a test run context for a new test run."""

    def prepare_test_run_async(
        self, ctx: ITestRunContext, test_names: Sequence[str]
    ) -> Awaitable[None]:
        """Prepare a new test run. Called once at the start of the test run,
        before run_test_async() is invoked for each test.
        """

    def run_warmup_compile_for_test_async(
        self, ctx: ITestRunContext, test_name: str
    ) -> Awaitable[None]:
        """Run a pre-test warmup compile step."""

    def run_test_async(
        self, ctx: ITestRunContext, test_name: str
    ) -> Awaitable[TestResult]:
        """Execute the specified test case."""


@runtime_checkable
class ITestReporter(Protocol):
    """Responsible for reporting the outcome of a test run."""

    def report_warmup_compile_started_async(self) -> Awaitable[None]:
        """Report that the warmup compile step has started."""

    def report_warmup_compile_progress_async(self, test_name: str) -> Awaitable[None]:
        """Report that the warmup compile step has finished processing the
        specified test.
        """

    def report_warmup_compile_ended_async(self) -> Awaitable[None]:
        """Report that the warmup compile step has ended."""

    def report_test_run_started_async(self) -> Awaitable[None]:
        """Report that the test run has started."""

    def report_test_result_async(
        self, test_name: str, test_passed: bool, test_result: TestResult
    ) -> Awaitable[None]:
        """Report the result of a single test case after having been run."""

    def report_test_run_result_async(self) -> Awaitable[None]:
        """Report the result of the overall test run. The reporter is expected
        to aggregate the information it has received about the result from
        each individual test case.
        """


@runtime_checkable
class ITestRunner(Protocol):
    """High-level interface for initating and carrying out a test run."""

    def run_async(self, test_names: Sequence[str]) -> Awaitable[int]:
        """Run the specified tests."""
