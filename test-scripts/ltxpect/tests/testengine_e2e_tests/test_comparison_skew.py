import asyncio
from dataclasses import dataclass
import os
import pathlib
import re
import sys
import unittest
from typing import Self, Sequence, Type, TypeVar

import ltxpect
import ltxpect.buildtools
import ltxpect.buildtools.ghostscript
import ltxpect.buildtools.imagemagick
import ltxpect.buildtools.pdfinfo
import ltxpect.paths
import ltxpect.testconfig
import ltxpect.testengine
import ltxpect.testresult
from ltxpect import asyncpopen
from ltxpect.coreabc import IFileSystem, IExternalProgramLocator, IPathUtil
from ltxpect.filesystem import FileSystem
from ltxpect.shutilexternalprogramlocator import ShutilExternalProgramLocator


def test_generator(
    path_util: IPathUtil,
    tex_tests_root_dir: str,
    test_file_prefix: str = "test",
):
    for dir_path, _dir_names, file_names in os.walk(tex_tests_root_dir):
        for file_name in file_names:
            # Ignore files that contain spaces
            if " " in file_name:
                continue

            if not file_name.startswith(test_file_prefix):
                continue

            if not file_name.endswith(".tex"):
                continue

            filebasename = os.path.splitext(file_name)[0]
            test_name = path_util.path_relpath(
                path_util.path_join(dir_path, filebasename), tex_tests_root_dir
            )

            yield test_name


fs = FileSystem()
path_util = ltxpect.paths.SystemPathUtil()


script_dir = str(pathlib.Path(__file__).parent.resolve())
comparison_skew_tests_dir = path_util.path_join(script_dir, "comparison_skew_tests")
assert fs.is_directory(comparison_skew_tests_dir)


@dataclass(frozen=True, slots=True, kw_only=True)
class ComparisonSkewTestConfig:
    ltx_test_name: str
    py_test_name: str
    build_dir: str
    tests_dir: str
    pdfs_dir: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ComparisonSkewTestCompileResult:
    texfile_abspath: str
    test_pdf_without_skew_path: str
    test_pdf_with_skew_path: str


class PdfLatexTestBuilder:
    def __init__(self, pflatex_cmd: Sequence[str], path_util: IPathUtil) -> None:
        self.pflatex_cmd = tuple(pflatex_cmd)
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

        cmd = list(self.pflatex_cmd) + [
            "-shell-escape",
            f"-jobname={latex_jobname}",
            f"-output-directory={latex_build_dir_relative_to_texfile_parent_dir}",
            "-interaction=nonstopmode",
            "-halt-on-error",
            texfile_filename,
        ]

        return await asyncpopen.popen_async(
            asyncio.get_running_loop(),
            cmd,
            cwd=texfile_parent_dir_path,
            timeout=timeout,
        )

    @classmethod
    def create(
        cls: Type[Self], path_util: IPathUtil, locator: IExternalProgramLocator
    ) -> Self:
        pdflatex_cmd = locator.find_program("pdfLaTeX", ["pdflatex"])
        return cls([pdflatex_cmd], path_util)


class ComparisonSkewTestPdfLatexBuilder:
    def __init__(self, pflatex_cmd: Sequence[str], path_util: IPathUtil) -> None:
        self.pflatex_cmd = tuple(pflatex_cmd)
        self.path_util = path_util

    async def build_latex_test_document_async(
        self,
        texfile_parent_dir_path: str,
        texfile_filename: str,
        latex_build_dir_path: str,
        with_skew: bool,
        timeout: float = 0,
    ) -> asyncpopen.AsyncPopenResult:
        latex_build_dir_relative_to_texfile_parent_dir = self.path_util.path_relpath(
            latex_build_dir_path, texfile_parent_dir_path
        )

        cmd = list(self.pflatex_cmd) + [
            "-shell-escape",
            "-jobname=output",
            f"-output-directory={latex_build_dir_relative_to_texfile_parent_dir}",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"\\let\\skew={1 if with_skew else 0}\\relax\\input{{{texfile_filename}}}",
        ]

        return await asyncpopen.popen_async(
            asyncio.get_running_loop(),
            cmd,
            cwd=texfile_parent_dir_path,
            timeout=timeout,
        )

    @classmethod
    def create(
        cls: Type[Self], path_util: IPathUtil, locator: IExternalProgramLocator
    ) -> Self:
        pdflatex_cmd = locator.find_program("pdfLaTeX", ["pdflatex"])
        return cls([pdflatex_cmd], path_util)


async def build_comparison_skew_test_tex_file_variants_async(
    config: ComparisonSkewTestConfig,
    path_util: IPathUtil,
    fs: IFileSystem,
    pdflatex_builder: ComparisonSkewTestPdfLatexBuilder,
) -> ComparisonSkewTestCompileResult:
    # Path to tex file, relative to config.tests_dir
    texfile_relpath = "{}.tex".format(config.ltx_test_name)

    texfile_parent_dir_relpath = os.path.dirname(texfile_relpath)
    texfile_filename = os.path.basename(texfile_relpath)
    texfile_basename = os.path.splitext(texfile_filename)[0]

    # Certain LaTeX versions have problems with build directory paths containing '[' and ']' characters
    # when going through MSYS->Windows path substitution
    texfile_basename_subst = (
        texfile_basename.replace("]", "").replace("[", "~").replace(",", "_")
        if re.search(r"\[.*\]", texfile_basename)
        else texfile_basename
    )

    texfile_parent_dir_path = path_util.path_join(
        config.tests_dir, texfile_parent_dir_relpath
    )
    assert fs.is_directory(texfile_parent_dir_path)

    texfile_abspath = path_util.path_join(texfile_parent_dir_path, texfile_filename)
    assert fs.is_file(texfile_abspath)

    # "Warmup" compile
    latex_build_dir = path_util.path_join(
        config.build_dir,
        texfile_parent_dir_relpath,
        texfile_basename_subst,
    )
    fs.force_remove_tree(latex_build_dir)
    fs.mkdirp(latex_build_dir)
    for _ in range(2):
        try:
            _ = await pdflatex_builder.build_latex_test_document_async(
                texfile_parent_dir_path=texfile_parent_dir_path,
                texfile_filename=texfile_filename,
                latex_build_dir_path=latex_build_dir,
                with_skew=False,
                timeout=30,
            )
        except:
            pass

    fs.force_remove_tree(latex_build_dir)

    test_pdf_without_skew_path = path_util.path_join(
        config.pdfs_dir, "{}__a.pdf".format(config.ltx_test_name)
    )
    test_pdf_with_skew_path = path_util.path_join(
        config.pdfs_dir, "{}__b.pdf".format(config.ltx_test_name)
    )

    for variant, test_pdf_path, with_skew in (
        ("a", test_pdf_without_skew_path, False),
        ("b", test_pdf_with_skew_path, True),
    ):
        latex_build_dir = (
            path_util.path_join(
                config.build_dir,
                texfile_parent_dir_relpath,
                texfile_basename_subst,
            )
            + f"__{variant}"
        )

        fs.force_remove_tree(latex_build_dir)
        fs.mkdirp(latex_build_dir)

        fs.mkdirp(os.path.dirname(test_pdf_path))
        fs.force_remove_file(test_pdf_path)

        returncode, stdout, stderr = (
            await pdflatex_builder.build_latex_test_document_async(
                texfile_parent_dir_path=texfile_parent_dir_path,
                texfile_filename=texfile_filename,
                latex_build_dir_path=latex_build_dir,
                with_skew=with_skew,
                timeout=30,
            )
        )
        assert returncode == 0

        latex_build_outdir_pdf_path = path_util.path_join(latex_build_dir, "output.pdf")

        fs.move_file(latex_build_outdir_pdf_path, test_pdf_path)
        fs.force_remove_tree(latex_build_dir)

    return ComparisonSkewTestCompileResult(
        texfile_abspath=texfile_abspath,
        test_pdf_without_skew_path=test_pdf_without_skew_path,
        test_pdf_with_skew_path=test_pdf_with_skew_path,
    )


SelfComparisonSkewTests = TypeVar(
    "SelfComparisonSkewTests", bound="ComparisonSkewTests"
)


class ComparisonSkewTestsMeta(type):
    def __new__(mcs, name, bases, namespace):
        def __generate_test_function(config: ComparisonSkewTestConfig):
            def __test_function(self: SelfComparisonSkewTests):
                async def test_async(config: ComparisonSkewTestConfig):
                    comparison_skew_test_pdflatex_builder = (
                        ComparisonSkewTestPdfLatexBuilder.create(
                            self.path_util, self.external_program_locator
                        )
                    )

                    compile_result = (
                        await build_comparison_skew_test_tex_file_variants_async(
                            config,
                            self.path_util,
                            self.fs,
                            comparison_skew_test_pdflatex_builder,
                        )
                    )

                    texfile_filename = os.path.basename(compile_result.texfile_abspath)
                    texfile_basename = os.path.splitext(texfile_filename)[0]

                    # Setup test directory for testing test engine
                    testengine_test_base_dir = path_util.path_join(
                        comparison_skew_tests_dir,
                        "ltxtest",
                    )
                    tests_dir = path_util.path_join(testengine_test_base_dir, "tests")
                    proto_dir = path_util.path_join(testengine_test_base_dir, "proto")

                    pdf_doc_info_provider = ltxpect.buildtools.pdfinfo.PdfDocInfoProviderUsingExternalPdfInfoProgram.create(
                        self.external_program_locator
                    )
                    pdf_page_rasterizer = ltxpect.buildtools.ghostscript.GhostScriptPdfPageRasterizer.create(
                        self.external_program_locator
                    )
                    png_dimensions_inspector = ltxpect.buildtools.imagemagick.ImageMagickPngImageDimensionsInspector.create(
                        self.external_program_locator
                    )
                    png_comparer = ltxpect.buildtools.imagemagick.ImageMagickPngImageComparer.create(
                        self.external_program_locator
                    )

                    latex_doc_buildtool = PdfLatexTestBuilder.create(
                        self.path_util, self.external_program_locator
                    )

                    test_engine_config = ltxpect.testconfig.TestConfig(
                        test_base_dir=testengine_test_base_dir, proto_dir="proto"
                    )

                    test_engine = ltxpect.testengine.TestEngine(
                        test_engine_config,
                        path_util=self.path_util,
                        fs=self.fs,
                        latex_doc_buildtool=latex_doc_buildtool,
                        pdf_doc_info_provider=pdf_doc_info_provider,
                        pdf_page_rasterizer=pdf_page_rasterizer,
                        png_dimensions_inspector=png_dimensions_inspector,
                        png_comparer=png_comparer,
                    )

                    # Pass 1 - compare test with PDF that should match

                    fs.force_remove_tree(testengine_test_base_dir)
                    fs.mkdirp(testengine_test_base_dir)
                    fs.mkdirp(tests_dir)
                    fs.mkdirp(proto_dir)

                    self.fs.copy_file(
                        compile_result.texfile_abspath,
                        path_util.path_join(tests_dir, texfile_filename),
                    )
                    self.fs.copy_file(
                        compile_result.test_pdf_without_skew_path,
                        path_util.path_join(proto_dir, f"{texfile_basename}.pdf"),
                    )

                    ctx = test_engine.create_test_run_context()
                    without_skew_test_result: ltxpect.testresult.TestResult = (
                        await test_engine.run_test_async(ctx, texfile_basename)
                    )

                    self.assertTrue(without_skew_test_result.build_succeeded)
                    self.assertEqual(without_skew_test_result.failed_pages, ())

                    # Pass 2 - compare test with PDF that should -not- match

                    fs.force_remove_tree(testengine_test_base_dir)
                    fs.mkdirp(testengine_test_base_dir)
                    fs.mkdirp(tests_dir)
                    fs.mkdirp(proto_dir)

                    self.fs.copy_file(
                        compile_result.texfile_abspath,
                        path_util.path_join(tests_dir, texfile_filename),
                    )
                    self.fs.copy_file(
                        compile_result.test_pdf_with_skew_path,
                        path_util.path_join(proto_dir, f"{texfile_basename}.pdf"),
                    )

                    ctx = test_engine.create_test_run_context()
                    with_skew_test_result: ltxpect.testresult.TestResult = (
                        await test_engine.run_test_async(ctx, texfile_basename)
                    )

                    self.assertTrue(with_skew_test_result.build_succeeded)
                    self.assertNotEqual(with_skew_test_result.failed_pages, ())

                    # Cleanup
                    fs.force_remove_tree(testengine_test_base_dir)
                    fs.force_remove_tree(config.build_dir)
                    fs.force_remove_tree(config.pdfs_dir)

                if sys.platform == "win32":
                    loop = asyncio.ProactorEventLoop()
                else:
                    loop = asyncio.SelectorEventLoop()

                try:
                    loop.run_until_complete(
                        asyncio.wait_for(test_async(config), timeout=10.0)
                    )
                finally:
                    loop.close()

            return __test_function

        tests_dir = path_util.path_join(comparison_skew_tests_dir, "test_cases")
        build_dir = path_util.path_join(comparison_skew_tests_dir, ".build")
        pdfs_dir = path_util.path_join(comparison_skew_tests_dir, "pdfs")

        for ltx_test_name in test_generator(
            path_util,
            tests_dir,
        ):
            py_test_name = "test__" + (
                ltx_test_name.split("[")[0].replace("\\", "__").replace("/", "__")
            )

            config = ComparisonSkewTestConfig(
                ltx_test_name=ltx_test_name,
                py_test_name=py_test_name,
                build_dir=build_dir,
                tests_dir=tests_dir,
                pdfs_dir=pdfs_dir,
            )
            namespace[py_test_name] = __generate_test_function(config)

        return type.__new__(mcs, name, bases, namespace)


class ComparisonSkewTests(unittest.TestCase, metaclass=ComparisonSkewTestsMeta):
    fs: IFileSystem
    path_util: IPathUtil
    external_program_locator: IExternalProgramLocator

    def setUp(self):
        self.fs = FileSystem()
        self.path_util = ltxpect.paths.SystemPathUtil()
        self.external_program_locator = ShutilExternalProgramLocator()
