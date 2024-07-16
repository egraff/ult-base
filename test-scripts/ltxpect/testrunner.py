import asyncio
from dataclasses import dataclass
from collections.abc import Sequence
from typing import TYPE_CHECKING

from .coreabc import IPathUtil, ITestEngine, ITestReporter, ITestRunContext, ITestRunner
from .testresult import TestResult


@dataclass(frozen=True, slots=True, kw_only=True)
class TestRunnerConfig:
    run_warmup_compile_before_tests: bool = False


class TestRunner:
    def __init__(
        self,
        config: TestRunnerConfig,
        engine: ITestEngine,
        reporter: ITestReporter,
        path_util: IPathUtil,
    ) -> None:
        self.config = config
        self.engine = engine
        self.reporter = reporter
        self.path_util = path_util

    async def run_async(self, test_names: Sequence[str]) -> int:
        ctx = self.engine.create_test_run_context()

        if self.config.run_warmup_compile_before_tests:
            await self._run_warmup_compile_async(ctx, test_names)

        return await self._run_tests_async(ctx, test_names)

    async def _run_warmup_compile_async(
        self, ctx: ITestRunContext, test_names: Sequence[str]
    ) -> None:
        await self.reporter.report_warmup_compile_started_async()

        # NOTE: warmup compile steps run sequentially
        for test_name in test_names:
            await self.engine.run_warmup_compile_for_test_async(ctx, test_name)

        await self.reporter.report_warmup_compile_ended_async()

    async def _run_test_async(self, ctx: ITestRunContext, test_name: str) -> bool:
        test_result: TestResult = await self.engine.run_test_async(ctx, test_name)
        assert test_result.test_name == test_name

        test_passed = (
            test_result.build_succeeded
            and (test_result.exc_info is None)
            and (len(test_result.failed_pages) == 0)
        )

        await self.reporter.report_test_result_async(
            test_name, test_passed, test_result
        )

        return test_passed

    async def _run_tests_async(
        self, ctx: ITestRunContext, test_names: Sequence[str]
    ) -> int:
        await self.reporter.report_test_run_started_async()

        test_futures: list[asyncio.Future[bool]] = []
        for test_name in test_names:
            test_future = asyncio.ensure_future(self._run_test_async(ctx, test_name))
            test_futures.append(test_future)

        done_futures, pending_futures = await asyncio.wait(test_futures)
        assert len(pending_futures) == 0

        results: list[bool] = []
        for future in done_futures:
            # Await to allow a potential exception to propagate
            try:
                test_passed = await future
                results.append(test_passed)
            except:
                # Observe all exceptions to suppress "Task exception was never retrieved" error
                # (we are only interested in the first exception)
                _ = [x.exception() for x in done_futures]

                # Re-raise just the first exception
                raise

        await self.reporter.report_test_run_result_async()

        return 0 if all(results) else 1


if TYPE_CHECKING:
    _: type[ITestRunner] = TestRunner
