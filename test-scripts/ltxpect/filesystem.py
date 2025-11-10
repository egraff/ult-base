import contextlib
import os
import shutil
from typing import TYPE_CHECKING

from .coreabc import IFileSystem


class FileSystem:
    def resolve_path(self, path: str) -> str:
        return os.path.realpath(path, strict=True)

    def is_file(self, path: str) -> bool:
        return os.path.isfile(path)

    def is_directory(self, path: str) -> bool:
        return os.path.isdir(path)

    def mkdirp(self, dirpath: str) -> None:
        try:
            os.makedirs(dirpath)
        except OSError:
            if not os.path.isdir(dirpath):
                raise

    def remove_file(self, filepath: str) -> None:
        try:
            os.remove(filepath)
        except OSError:
            raise

    def force_remove_file(self, filepath: str) -> None:
        with contextlib.suppress(FileNotFoundError):
            os.remove(filepath)

    def force_remove_tree(self, dirpath: str) -> None:
        shutil.rmtree(dirpath, ignore_errors=True)

    def move_directory(self, oldpath: str, newpath: str) -> None:
        shutil.move(oldpath, newpath)

    def move_file(self, oldpath: str, newpath: str) -> None:
        shutil.move(oldpath, newpath)

    def copy_file(self, oldpath: str, newpath: str) -> None:
        shutil.copyfile(oldpath, newpath)


if TYPE_CHECKING:
    _: type[IFileSystem] = FileSystem
