import argparse
import asyncio
import os
import re
import sys
from typing import cast, Callable

import ltxpect
import ltxpect.buildtools
import ltxpect.buildtools.ghostscript
import ltxpect.buildtools.imagemagick
import ltxpect.buildtools.misc
import ltxpect.buildtools.pdfinfo
import ltxpect.coreabc
import ltxpect.paths
from ltxpect.aggregatereporter import AggregateReporter
from ltxpect.colorconsolereporter import ColorConsoleReporter
from ltxpect.filesystem import FileSystem
from ltxpect.shutilexternalprogramlocator import ShutilExternalProgramLocator
from ltxpect.testresultsjsonreporter import TestResultsJsonReporter
from ltxpect.testconfig import TestConfig
from ltxpect.testengine import TestEngine
from ltxpect.testrunner import TestRunner, TestRunnerConfig


def test_generator(
    path_util: ltxpect.coreabc.IPathUtil,
    tex_tests_root_dir: str,
    test_file_prefix: str = "test",
    test_name_filter: Callable[[str], bool] | None = None,
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

            if test_name_filter and not test_name_filter(test_name):
                continue

            yield test_name


def _dirname(val) -> str:
    assert isinstance(val, str)

    if (os.path.sep in val) or ("/" in val) or (".." in val):
        raise argparse.ArgumentTypeError("should be a folder name, not a path")

    return val


def _str2bool(val: str) -> bool:
    assert isinstance(val, str)

    if val.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif val.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError(f"Boolean value expected, got {val}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "test_base_dir",
        metavar="<test base folder>",
        type=str,
        help="the base folder for the tests",
    )
    parser.add_argument(
        "--test",
        dest="test_name",
        type=str,
        default=None,
        help="the name of a specific test to run",
    )
    parser.add_argument(
        "--filter",
        dest="test_filter",
        type=str,
        default=None,
        help="a regular expression filter determining which tests to run",
    )
    parser.add_argument(
        "--protodir",
        dest="proto_dir",
        type=_dirname,
        default="proto",
        help="the name of the test prototype folder",
    )
    parser.add_argument(
        "--warmup-compile",
        dest="run_warmup_compile_before_tests",
        type=_str2bool,
        default=False,
        help="whether to run a warmup compile step before executing the tests",
    )

    args = parser.parse_args()

    path_util = ltxpect.paths.SystemPathUtil()

    external_program_locator = ShutilExternalProgramLocator()
    pdf_doc_info_provider = (
        ltxpect.buildtools.pdfinfo.PdfDocInfoProviderUsingExternalPdfInfoProgram.create(
            external_program_locator
        )
    )
    pdf_page_rasterizer = (
        ltxpect.buildtools.ghostscript.GhostScriptPdfPageRasterizer.create(
            external_program_locator
        )
    )
    png_dimensions_inspector = (
        ltxpect.buildtools.imagemagick.ImageMagickPngImageDimensionsInspector.create(
            external_program_locator
        )
    )
    png_comparer = ltxpect.buildtools.imagemagick.ImageMagickPngImageComparer.create(
        external_program_locator
    )

    test_base_dir = args.test_base_dir
    tex_tests_root_dir = path_util.path_join(test_base_dir, "tests")

    test_config = TestConfig(
        test_base_dir=test_base_dir,
        proto_dir=args.proto_dir,
        num_concurrent_processes=min(max(int(1.5 * cast(int, os.cpu_count())), 2), 16),
    )
    test_runner_config = TestRunnerConfig(
        run_warmup_compile_before_tests=args.run_warmup_compile_before_tests,
    )

    engine = TestEngine(
        test_config,
        path_util=path_util,
        fs=FileSystem(),
        latex_doc_buildtool=ltxpect.buildtools.misc.MakefileTestBuilder(path_util),
        pdf_doc_info_provider=pdf_doc_info_provider,
        pdf_page_rasterizer=pdf_page_rasterizer,
        png_dimensions_inspector=png_dimensions_inspector,
        png_comparer=png_comparer,
    )

    reporter = AggregateReporter(
        [
            TestResultsJsonReporter(
                path_util.path_join(test_base_dir, "test_result.json")
            ),
            ColorConsoleReporter(),
        ]
    )

    runner = TestRunner(test_runner_config, engine, reporter, path_util)

    if args.test_name is not None:
        tests = [args.test_name]
    else:
        test_name_filter = None
        if args.test_filter:
            test_name_filter = lambda x: re.search(args.test_filter, x) is not None

        tests = [
            test_name
            for test_name in test_generator(
                path_util, tex_tests_root_dir, test_name_filter=test_name_filter
            )
        ]

    retcode = asyncio.run(runner.run_async(tests))
    sys.exit(retcode)
