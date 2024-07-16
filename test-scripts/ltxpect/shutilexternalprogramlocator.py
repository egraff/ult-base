import os
import shutil
from typing import TYPE_CHECKING

from .coreabc import IExternalProgramLocator


class ShutilExternalProgramLocator:
    def __init__(self) -> None:
        self._found_cmds: dict[str, str] = {}

    def find_program(self, appname: str, app_cmd_candidates: list[str]) -> str:
        for cmd in app_cmd_candidates:
            if cmd in self._found_cmds:
                return self._found_cmds[cmd]

        for cmd in app_cmd_candidates:
            cmd_path = shutil.which(cmd)
            if cmd_path:
                cmd_name = os.path.basename(cmd_path)
                self._found_cmds[cmd] = cmd_name
                return cmd_name

        raise Exception(
            f"The external program '{appname}' could not be found in the system! Have you installed it?"
        )


if TYPE_CHECKING:
    _: type[IExternalProgramLocator] = ShutilExternalProgramLocator  # type: ignore[no-redef]
