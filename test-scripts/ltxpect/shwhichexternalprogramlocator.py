import os
import subprocess
from typing import TYPE_CHECKING

from .coreabc import IExternalProgramLocator


class ShWhichExternalProgramLocator:
    def __init__(self) -> None:
        self._found_cmds: dict[str, str] = {}

    def find_program(self, appname: str, app_cmd_candidates: list[str]) -> str:
        which_command = self._create_which_command_for_app_list(app_cmd_candidates)

        which_app = subprocess.Popen(
            ["sh", "-c", which_command],
            env=os.environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, _stderr = which_app.communicate()
        which_app.wait()

        app = stdout.strip().decode("utf-8")

        if not app:
            raise Exception(
                f"The external program '{appname}' could not be found in the system! Have you installed it?"
            )

        return os.path.basename(app)

    @staticmethod
    def _create_which_command_for_app_list(app_cmd_candidates: list[str]) -> str:
        return "||".join(f"which {cmd}" for cmd in app_cmd_candidates)


if TYPE_CHECKING:
    _: type[IExternalProgramLocator] = ShWhichExternalProgramLocator
