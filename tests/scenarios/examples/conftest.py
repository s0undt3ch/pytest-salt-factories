import shutil
from pathlib import Path
from typing import Any
from typing import Callable

import attr
import pytest

from saltfactories import CODE_ROOT_DIR
from saltfactories.utils.virtualenv import VirtualEnv


@attr.s(kw_only=True, slots=True, frozen=True)
class ExtensionVirtualEnv(VirtualEnv):
    extension_path: Path = attr.ib()
    tmp_path: Path = attr.ib()
    copy_path: Path = attr.ib(init=False)
    venv: VirtualEnv = attr.ib(init=False)

    @copy_path.default
    def _default_copy_path(self) -> Path:
        _copy_path = self.tmp_path / "code"
        shutil.copytree(str(self.extension_path), str(_copy_path))
        return _copy_path

    @venv.default
    def _init_virtualenv(self) -> VirtualEnv:
        return VirtualEnv(self.tmp_path / ".venv", cwd=self.copy_path)

    def __enter__(self) -> VirtualEnv:  # noqa: D105
        self.venv.__enter__()
        self.venv.run("git", "init", ".")
        self.venv.run("git", "add", ".")
        self.venv.install(str(CODE_ROOT_DIR.parent.parent))
        # Salt(3003) doesn't yet support pyzmq 21.0.x
        self.venv.install("pyzmq<21.0.0")
        self.venv.install(".[tests]")
        return self.venv

    def __exit__(self, *_: Any) -> None:  # noqa: D105
        self.venv.__exit__(*_)


@pytest.fixture
def extension_venv(tmp_path: Path) -> Callable[[Path], ExtensionVirtualEnv]:
    def create_extension_virtualenv(extension_path: Path) -> ExtensionVirtualEnv:
        return ExtensionVirtualEnv(extension_path=extension_path, tmp_path=tmp_path)

    return create_extension_virtualenv
