import asyncio
import os
import sys
import unittest
import unittest.mock as mock
from typing import Any, Callable, cast

from ltxpect import asyncpopen


class FakeTransport(asyncio.SubprocessTransport):
    def __init__(self, transport_closed_future: asyncio.Future[None]) -> None:
        self._has_returncode = False
        self._transport_closed_future = transport_closed_future

    def set_protocol(self, protocol: asyncio.BaseProtocol) -> None:
        """Set a new protocol."""
        self._protocol = protocol

    def get_protocol(self) -> asyncio.BaseProtocol:
        """Return the current protocol."""
        return self._protocol

    def close(self) -> None:
        self._transport_closed_future.set_result(None)

    def terminate(self) -> None:
        return self.close()

    def set_returncode(self, returncode: int):
        self._returncode = returncode
        self._has_returncode = True

    def get_returncode(self) -> int | None:
        if not self._has_returncode:
            raise Exception("Test must set returncode before completing process")

        return self._returncode


class AsyncPopenTests(unittest.TestCase):
    def setUp(self) -> None:
        if sys.platform == "win32":
            self.loop = asyncio.ProactorEventLoop()
        else:
            self.loop = asyncio.SelectorEventLoop()

        patcher = mock.patch.object(
            self.loop, "subprocess_exec", new_callable=mock.AsyncMock
        )
        self.subprocess_exec_mock = patcher.start()
        self.addCleanup(patcher.stop)

        self.transport_closed_future = cast(
            asyncio.Future[None], self.loop.create_future()
        )

        self.transport = FakeTransport(
            transport_closed_future=self.transport_closed_future
        )
        self.subprocess_exec_called_future = cast(
            asyncio.Future[
                tuple[asyncio.BaseProtocol, str, tuple[str, ...], dict[str, Any]]
            ],
            self.loop.create_future(),
        )

        # Configure "happy path" as default behaviour
        def subprocess_exec(
            protocol_factory: Callable[[], asyncio.BaseProtocol],
            program: str,
            *args: str,
            **kwargs
        ) -> tuple[asyncio.SubprocessTransport, asyncio.SubprocessProtocol]:
            protocol = protocol_factory()
            assert isinstance(protocol, asyncio.SubprocessProtocol)

            self.transport.set_protocol(protocol)

            self.subprocess_exec_called_future.set_result(
                (protocol, program, args, kwargs)
            )

            return (self.transport, protocol)

        self.subprocess_exec_mock.side_effect = subprocess_exec
        self.subprocess_exec_mock.reset_mock()

    def test_subprocess_arguments__with_default_environment(self) -> None:
        # Arrange

        async def test_async():
            # Act

            popen_task = asyncio.create_task(
                asyncpopen.popen_async(
                    asyncio.get_running_loop(),
                    ["/path/to/program", "first_arg", "--second_arg"],
                    timeout=123,
                )
            )

            # Assert

            # Use asyncio.wait() in case there was an exception from popen_async()
            done_futures, _ = await asyncio.wait(
                [self.subprocess_exec_called_future, popen_task],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=1.0,
            )
            if popen_task in done_futures:
                await popen_task
                self.fail("popen_async() returned unexpectedly")

            protocol, program, program_args, subprocess_exec_kwargs = (
                await self.subprocess_exec_called_future
            )

            self.assertEqual(program, "/path/to/program")
            self.assertEqual(program_args, ("first_arg", "--second_arg"))
            self.assertEqual(subprocess_exec_kwargs, {"env": os.environ})

            # Cleanup

            protocol.connection_made(self.transport)
            self.transport.set_returncode(123)
            protocol.connection_lost(None)
            await asyncio.wait([popen_task, self.transport_closed_future])

        try:
            self.loop.run_until_complete(asyncio.wait_for(test_async(), timeout=1.0))
        finally:
            self.loop.close()

    def test_subprocess_arguments__with_user_specified_environment(self) -> None:
        # Arrange

        async def test_async():
            # Act

            popen_task = asyncio.create_task(
                asyncpopen.popen_async(
                    asyncio.get_running_loop(),
                    ["/path/to/program", "first_arg", "--second_arg"],
                    timeout=123,
                    env={"ENV_A": "A", "ENV_B": "B"},
                )
            )

            # Assert

            # Use asyncio.wait() in case there was an exception from popen_async()
            done_futures, _ = await asyncio.wait(
                [self.subprocess_exec_called_future, popen_task],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=1.0,
            )
            if popen_task in done_futures:
                await popen_task
                self.fail("popen_async() returned unexpectedly")

            protocol, program, program_args, subprocess_exec_kwargs = (
                await self.subprocess_exec_called_future
            )

            self.assertEqual(program, "/path/to/program")
            self.assertEqual(program_args, ("first_arg", "--second_arg"))
            self.assertEqual(
                subprocess_exec_kwargs, {"env": {"ENV_A": "A", "ENV_B": "B"}}
            )

            # Cleanup

            protocol.connection_made(self.transport)
            self.transport.set_returncode(123)
            protocol.connection_lost(None)
            await asyncio.wait([popen_task, self.transport_closed_future])

        try:
            self.loop.run_until_complete(asyncio.wait_for(test_async(), timeout=1.0))
        finally:
            self.loop.close()

    def test_program_terminates_with_no_output(self) -> None:
        # Arrange

        async def test_async():
            popen_task = asyncio.create_task(
                asyncpopen.popen_async(
                    asyncio.get_running_loop(), ["A", "B", "C"], timeout=123, env={}
                )
            )

            # Use asyncio.wait() in case there was an exception from popen_async()
            done_futures, _ = await asyncio.wait(
                [self.subprocess_exec_called_future, popen_task],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=1.0,
            )
            if popen_task in done_futures:
                await popen_task
                self.fail("popen_async() returned unexpectedly")

            protocol, *_ = await self.subprocess_exec_called_future
            protocol.connection_made(self.transport)

            # Act

            self.transport.set_returncode(123)
            protocol.connection_lost(None)

            # Assert

            await self.transport_closed_future

            result = await popen_task
            self.assertEqual(result.returncode, 123)
            self.assertEqual(result.stdout, ())
            self.assertEqual(result.stderr, ())

        try:
            self.loop.run_until_complete(asyncio.wait_for(test_async(), timeout=1.0))
        finally:
            self.loop.close()

    def test_program_terminates_with_output(self) -> None:
        # Arrange

        async def test_async():
            popen_task = asyncio.create_task(
                asyncpopen.popen_async(
                    asyncio.get_running_loop(), ["A", "B", "C"], timeout=123, env={}
                )
            )

            # Use asyncio.wait() in case there was an exception from popen_async()
            done_futures, _ = await asyncio.wait(
                [self.subprocess_exec_called_future, popen_task],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=1.0,
            )
            if popen_task in done_futures:
                await popen_task
                self.fail("popen_async() returned unexpectedly")

            protocol, *_ = await self.subprocess_exec_called_future
            protocol.connection_made(self.transport)

            # Act

            protocol.pipe_data_received(1, b"First")
            protocol.pipe_data_received(1, b" stdout")
            protocol.pipe_data_received(2, b"First stderr")
            protocol.pipe_data_received(1, b" line")
            protocol.pipe_data_received(2, b" line\nSecond stderr")
            protocol.pipe_data_received(1, b"\nSecond stdout line\nLast stdout line")
            protocol.pipe_data_received(2, b" line\nLast stderr line\n")

            self.transport.set_returncode(123)
            protocol.connection_lost(None)

            # Assert

            await self.transport_closed_future

            result = await popen_task
            self.assertEqual(result.returncode, 123)
            self.assertEqual(
                result.stdout,
                (b"First stdout line", b"Second stdout line", b"Last stdout line"),
            )
            self.assertEqual(
                result.stderr,
                (b"First stderr line", b"Second stderr line", b"Last stderr line"),
            )

        try:
            self.loop.run_until_complete(asyncio.wait_for(test_async(), timeout=1.0))
        finally:
            self.loop.close()

    def test_program_times_out_with_no_output(self) -> None:
        # Arrange

        async def test_async():
            # Act

            popen_task = asyncio.create_task(
                asyncpopen.popen_async(
                    asyncio.get_running_loop(), ["A", "B", "C"], timeout=0.2, env={}
                )
            )

            # Assert

            # Use asyncio.wait() in case there was an exception from popen_async()
            done_futures, _ = await asyncio.wait(
                [self.subprocess_exec_called_future, popen_task],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=1.0,
            )
            if popen_task in done_futures:
                await popen_task
                self.fail("popen_async() returned unexpectedly")

            protocol, *_ = await self.subprocess_exec_called_future
            protocol.connection_made(self.transport)

            # Wait for call to transport.close() (due to timeout), and call
            # protocol's connection_lost() as a result
            await self.transport_closed_future
            self.transport.set_returncode(-1)
            protocol.connection_lost(None)

            with self.assertRaises(asyncpopen.AsyncPopenTimeoutError) as exctx:
                await popen_task

            self.assertEqual(
                exctx.exception.args[0],
                "The wait for the process to complete timed out",
            )

            self.assertEqual(exctx.exception.returncode, -1)
            self.assertEqual(
                exctx.exception.stdout,
                (),
            )
            self.assertEqual(
                exctx.exception.stderr,
                (),
            )

        try:
            self.loop.run_until_complete(asyncio.wait_for(test_async(), timeout=1.0))
        finally:
            self.loop.close()

    def test_program_times_out_with_output(self) -> None:
        # Arrange

        async def test_async():
            # Act

            popen_task = asyncio.create_task(
                asyncpopen.popen_async(
                    asyncio.get_running_loop(), ["A", "B", "C"], timeout=0.2, env={}
                )
            )

            # Assert

            # Use asyncio.wait() in case there was an exception from popen_async()
            done_futures, _ = await asyncio.wait(
                [self.subprocess_exec_called_future, popen_task],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=1.0,
            )
            if popen_task in done_futures:
                await popen_task
                self.fail("popen_async() returned unexpectedly")

            protocol, *_ = await self.subprocess_exec_called_future
            protocol.connection_made(self.transport)

            protocol.pipe_data_received(1, b"First")
            protocol.pipe_data_received(1, b" stdout")
            protocol.pipe_data_received(2, b"First stderr")
            protocol.pipe_data_received(1, b" line")
            protocol.pipe_data_received(2, b" line\nSecond stderr")
            protocol.pipe_data_received(1, b"\nSecond stdout line\nLast stdout line")
            protocol.pipe_data_received(2, b" line\nLast stderr line\n")

            # Wait for call to transport.close() (due to timeout), and call
            # protocol's connection_lost() as a result
            await self.transport_closed_future
            self.transport.set_returncode(-1)
            protocol.connection_lost(None)

            with self.assertRaises(asyncpopen.AsyncPopenTimeoutError) as exctx:
                await popen_task

            self.assertEqual(
                exctx.exception.args[0],
                "The wait for the process to complete timed out",
            )

            self.assertEqual(exctx.exception.returncode, -1)
            self.assertEqual(
                exctx.exception.stdout,
                (b"First stdout line", b"Second stdout line", b"Last stdout line"),
            )
            self.assertEqual(
                exctx.exception.stderr,
                (b"First stderr line", b"Second stderr line", b"Last stderr line"),
            )

        try:
            self.loop.run_until_complete(asyncio.wait_for(test_async(), timeout=1.0))
        finally:
            self.loop.close()

    def test_subprocess_exec_raises_exception(self) -> None:
        # Arrange

        def subprocess_exec(protocol_factory, program, *args, **kwargs):
            raise ValueError("OOPS")

        self.subprocess_exec_mock.side_effect = subprocess_exec

        async def test_async():
            # Act

            popen_task = asyncio.create_task(
                asyncpopen.popen_async(
                    asyncio.get_running_loop(), ["A", "B", "C"], timeout=0.2, env={}
                )
            )

            # Assert

            with self.assertRaises(ValueError) as exctx:
                await popen_task

            self.assertEqual(exctx.exception.args[0], "OOPS")

        try:
            self.loop.run_until_complete(asyncio.wait_for(test_async(), timeout=1.0))
        finally:
            self.loop.close()
