import asyncio
import os
from typing import Awaitable, cast, Mapping, NamedTuple


class AsyncPopenResult(NamedTuple):
    """The result from running a child process, after it has terminated."""

    returncode: int
    """The exit code of the child process. Typically, an exit code 0 indicates
    that it ran successfully.
    """

    stdout: tuple[bytes, ...]
    """Captured stdout from the child process, as a list of lines."""

    stderr: tuple[bytes, ...]
    """Captured stderr from the child process, as a list of lines."""


class AsyncPopenTimeoutError(Exception):
    """An error that is thrown if the wait for a child process to complete
    times out.
    """

    def __init__(
        self,
        returncode: int,
        stdout: tuple[bytes, ...],
        stderr: tuple[bytes, ...],
    ) -> None:
        super().__init__("The wait for the process to complete timed out")
        self._returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    @property
    def returncode(self) -> int:
        """The exit code of the child process. Typically, an exit code 0 indicates
        that it ran successfully.
        """
        return self._returncode

    @property
    def stdout(self) -> tuple[bytes, ...]:
        """Captured stdout from the child process, as a list of lines."""
        return self._stdout

    @property
    def stderr(self) -> tuple[bytes, ...]:
        """Captured stderr from the child process, as a list of lines."""
        return self._stderr


class _AsyncProcessProtocol(asyncio.SubprocessProtocol):
    STDOUT = 1
    STDERR = 2

    def __init__(self, completed_future: asyncio.Future[AsyncPopenResult]) -> None:
        self._completed_future = completed_future
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._transport: asyncio.SubprocessTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        assert isinstance(transport, asyncio.SubprocessTransport)
        self._transport = transport

    def pipe_data_received(self, fd: int, data: bytes) -> None:
        if fd == self.STDOUT:
            self._stdout.extend(data)
        elif fd == self.STDERR:
            self._stderr.extend(data)

    # Note: we use connection_lost() instead of process_exited(), because it seems that stdout and stderr data might
    # not be flushed when process_exited() is called, whereas the Python documentation states that
    #   "After all buffered data is flushed, the protocol’s protocol.connection_lost() method will be called with None as its argument."
    # and we have not seen problems when relying on connection_lost() instead of process_exited().
    def connection_lost(self, exc: Exception | None) -> None:
        assert self._transport is not None

        returncode = self._transport.get_returncode()
        assert isinstance(returncode, int)

        stdout = tuple(bytes(line) for line in self._stdout.splitlines())
        stderr = tuple(bytes(line) for line in self._stderr.splitlines())

        self._completed_future.set_result(AsyncPopenResult(returncode, stdout, stderr))


async def popen_async(
    loop: asyncio.AbstractEventLoop,
    args: list[str],
    timeout: float = 0,
    env: Mapping[str, str] | None = None,
) -> AsyncPopenResult:
    """Run the (non-interactive) command described by args as a child process,
    and wait for the process to terminate (with an optional timeout).
    """
    if env is None:
        env = os.environ

    completed_future = cast(asyncio.Future[AsyncPopenResult], loop.create_future())

    transport, _protocol = await loop.subprocess_exec(
        lambda: _AsyncProcessProtocol(completed_future), *args, env=env
    )

    try:
        to_await: Awaitable[AsyncPopenResult] = completed_future
        if timeout > 0:
            # Note: need to shield the completed_future, to be able to do another
            # await for it below without getting an InvalidStateError
            to_await = asyncio.wait_for(asyncio.shield(to_await), timeout)

        returncode, stdout, stderr = await to_await
    except (asyncio.CancelledError, asyncio.TimeoutError):
        transport.close()
        returncode, stdout, stderr = await completed_future

        raise AsyncPopenTimeoutError(returncode, stdout, stderr)
    else:
        transport.close()

    return AsyncPopenResult(returncode, stdout, stderr)
