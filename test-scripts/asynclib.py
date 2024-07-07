import asyncio
import os
from typing import Awaitable, List, Tuple


class _AsyncProcessProtocol(asyncio.SubprocessProtocol):
    STDOUT = 1
    STDERR = 2

    def __init__(self, completed_future):
        self._completed_future = completed_future
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._transport = None

    def connection_made(self, transport):
        self._transport = transport

    def pipe_data_received(self, fd: int, data: bytes):
        if fd == self.STDOUT:
            self._stdout.extend(data)
        elif fd == self.STDERR:
            self._stderr.extend(data)

    # Note: we use connection_lost() instead of process_exited(), because it seems that stdout and stderr data might
    # not be flushed when process_exited() is called, whereas the Python documentation states that
    #   "After all buffered data is flushed, the protocol’s protocol.connection_lost() method will be called with None as its argument."
    # and we have not seen problems when relying on connection_lost() instead of process_exited().
    def connection_lost(self, exc):
        returncode = self._transport.get_returncode()
        stdout = self._stdout.splitlines() if self._stdout is not None else []
        stderr = self._stderr.splitlines() if self._stderr is not None else []

        self._completed_future.set_result((returncode, stdout, stderr))


class AsyncPopenTimeoutError(Exception):
    def __init__(self, returncode, stdout, stderr):
        super().__init__(self, "The wait for the process to complete timed out")
        self._returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    @property
    def returncode(self):
        return self._returncode

    @property
    def stdout(self):
        return self._stdout

    @property
    def stderr(self):
        return self._stderr


async def popen_async(
    args: List[str], timeout: float = 0, raise_exception_on_timeout=False
) -> Awaitable[Tuple[int, List[str], List[str]]]:
    try:
        loop = asyncio.get_running_loop()
    except AttributeError:
        loop = asyncio.get_event_loop()

    completed_future = loop.create_future()

    transport, protocol = await loop.subprocess_exec(
        lambda: _AsyncProcessProtocol(completed_future), *args, env=os.environ
    )

    try:
        task = asyncio.ensure_future(completed_future)
        if timeout > 0:
            # Note: need to shield the completed_future, to be able to do another
            # await for it below without getting an InvalidStateError
            task = asyncio.wait_for(asyncio.shield(task), timeout)

        returncode, stdout, stderr = await task
    except (asyncio.CancelledError, asyncio.TimeoutError):
        transport.close()
        returncode, stdout, stderr = await completed_future

        if raise_exception_on_timeout:
            raise AsyncPopenTimeoutError(returncode, stdout, stderr)

        # Instead of re-raising exception, ensure non-zero returncode
        if returncode == 0:
            returncode = -9
    else:
        transport.close()

    return (returncode, stdout, stderr)
