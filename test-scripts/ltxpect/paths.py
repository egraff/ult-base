import os
from typing import TYPE_CHECKING

from .coreabc import IPathUtil


class SystemPathUtil:
    def _normalize_path_separators(self, path: str) -> str:
        return path.replace("\\", "/")

    def path_join(self, path: str, *paths: str) -> str:
        return self._normalize_path_separators(os.path.join(path, *paths))

    def path_relpath(self, path: str, start: str = os.curdir) -> str:
        return self._normalize_path_separators(os.path.relpath(path, start))


if TYPE_CHECKING:
    _: type[IPathUtil] = SystemPathUtil
