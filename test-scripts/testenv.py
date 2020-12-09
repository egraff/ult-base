from typing import List
import os
import subprocess


def __create_which_command_for_app_list(app_list: List[str]) -> str:
    if isinstance(app_list, str):
        app_list = [app_list]

    return "||".join("which %s" % (app,) for app in app_list)


def __locate_test_utility(app_name: str, app_cmds: List[str]) -> str:
    which_command = __create_which_command_for_app_list(app_cmds)

    which_app = subprocess.Popen(
        ["sh", "-c", which_command],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout, stderr = which_app.communicate()
    which_app.wait()

    app = stdout.strip().decode("utf-8")

    if not len(app):
        raise Exception(
            "The test utility %s could not be found in the system! Have you installed it?"
            % (app_name,)
        )

    return os.path.basename(app)


def find_pdfinfo() -> str:
    return __locate_test_utility("PDFInfo", "pdfinfo")


def find_ghostscript() -> str:
    return __locate_test_utility("GhostScript", ["gs", "gswin64c", "gswin32c"])


def find_compare() -> str:
    return __locate_test_utility("Compare (ImageMagick)", "compare")


def find_identify() -> str:
    return __locate_test_utility("Identify (ImageMagick)", "identify")
