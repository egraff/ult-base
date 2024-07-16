from dataclasses import dataclass
from types import TracebackType
from typing import Optional, Type


@dataclass(frozen=True, slots=True)
class TestResult:
    test_name: str
    """The test name."""

    build_succeeded: bool
    """Whether the test's build step succeeded."""

    build_timed_out: bool = False
    """Whether test's build step timed out. Note that build_timed_out == True
    should imply build_succeeded == False.
    """

    exc_info: Optional[tuple[Type[BaseException], BaseException, TracebackType]] = None
    """Exception info that is set if there was an exception during any part of
    the test execution.
    """

    build_returncode: Optional[int] = None
    """The return code from the test's build step. Only set if the build step
    completed and build_succeeded == False.
    """

    build_stdout: tuple[bytes, ...] = ()
    """The captured stdout from the test's build step. Only set if the build
    step completed and build_succeeded == False.
    """

    build_stderr: tuple[bytes, ...] = ()
    """The captured stderr from the test's build step. Only set if the build
    step completed and build_succeeded == False.
    """

    build_logfile: Optional[str] = None
    """The relative path (from test_base_dir) to the log file from the test's
    build step, if it exists. Only set if the build step completed,
    build_succeeded == False, and the log file exists.
    """

    failed_pages: tuple[int, ...] = ()
    """The page numbers of all pages in the test document that failed the
    comparison check. Only set if the test's build step completed successfully.
    """
