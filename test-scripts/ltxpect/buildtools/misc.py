import asyncio
from typing import TYPE_CHECKING

from ltxpect import asyncpopen
from ltxpect.coreabc import IPathUtil
from .abc import ILatexDocumentBuildTool


class MakefileTestBuilder:
    def __init__(self, path_util: IPathUtil) -> None:
        self.path_util = path_util

    async def build_latex_document_async(
        self,
        base_dir: str,
        texfile_parent_dir_subpath: str,
        texfile_filename: str,
        latex_build_dir_subpath: str,
        latex_jobname: str,
        timeout: float = 0,
    ) -> asyncpopen.AsyncPopenResult:
        # Absolute path to the directory that contains the tex file
        texfile_parent_dir_path = self.path_util.path_join(
            base_dir, texfile_parent_dir_subpath
        )

        latex_build_dir_path = self.path_util.path_join(
            base_dir, latex_build_dir_subpath
        )

        latex_build_dir_relative_to_texfile_parent_dir = self.path_util.path_relpath(
            latex_build_dir_path, texfile_parent_dir_path
        )

        cmd = [
            "make",
            "-C",
            base_dir,
            "--no-print-directory",
            "_file",
            "LATEXMK=latexmk",
            "PDFLATEX=pdflatex",
            "MAKEGLOSSARIES=makeglossaries",
            "TEXFILE_DIR={}".format(texfile_parent_dir_subpath),
            "TEXFILE_FILENAME={}".format(texfile_filename),
            "LATEX_OUTPUT_DIR={}".format(
                latex_build_dir_relative_to_texfile_parent_dir
            ),
            "LATEX_JOBNAME={}".format(latex_jobname),
        ]

        return await asyncpopen.popen_async(
            asyncio.get_running_loop(), cmd, timeout=timeout
        )


if TYPE_CHECKING:
    _: type[ILatexDocumentBuildTool] = MakefileTestBuilder
