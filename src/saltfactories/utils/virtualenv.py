"""
VirtualEnv helper class.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any
from typing import cast
from typing import Dict
from typing import List
from typing import Optional

import attr
from pytestshellutils.customtypes import EnvironDict
from pytestshellutils.exceptions import ProcessFailed
from pytestshellutils.utils.processes import ProcessResult
from pytestskipmarkers.utils import platform

from saltfactories.utils import cast_to_pathlib_path

log = logging.getLogger(__name__)


@attr.s(frozen=True, slots=True)
class VirtualEnv:
    """
    Helper class to create and use a virtual environment.

    Keyword Arguments:
        venv_dir:
            The path to the directory where the virtual environment should be created
        venv_create_args:
            Additional list of strings to pass when creating the virtualenv
        env:
            Additional environment entries
        cwd:
            The default ``cwd`` to use. Can be overridden when calling
            :py:func:`~saltfactories.utils.virtualenv.VirtualEnv.run` and
            :py:func:`~saltfactories.utils.virtualenv.VirtualEnv.install`

        .. code-block:: python

            with VirtualEnv("/tmp/venv") as venv:
                venv.install("pep8")

                assert "pep8" in venv.get_installed_packages()
    """

    venv_dir: Path = attr.ib(converter=cast_to_pathlib_path)
    venv_create_args: List[str] = attr.ib(default=attr.Factory(list))
    env: Optional[EnvironDict] = attr.ib(default=None)
    cwd: Path = attr.ib(default=None)
    environ: EnvironDict = attr.ib(init=False, repr=False)
    venv_python: str = attr.ib(init=False, repr=False)
    venv_bin_dir: Path = attr.ib(init=False, repr=False)

    @venv_dir.default
    def _default_venv_dir(self) -> pathlib.Path:
        return pathlib.Path(tempfile.mkdtemp(dir=tempfile.gettempdir()))

    @environ.default
    def _default_environ(self) -> EnvironDict:
        environ = cast(EnvironDict, os.environ.copy())
        if self.env:
            environ.update(self.env)
        return environ

    @venv_python.default
    def _default_venv_python(self) -> str:
        # Once we drop Py3.5 we can stop casting to string
        if platform.is_windows():
            return str(self.venv_dir / "Scripts" / "python.exe")
        return str(self.venv_dir / "bin" / "python")

    @venv_bin_dir.default
    def _default_venv_bin_dir(self) -> pathlib.Path:
        return pathlib.Path(self.venv_python).parent

    def __enter__(self) -> VirtualEnv:
        """
        Use as a context manager.
        """
        try:
            self._create_virtualenv()
        except subprocess.CalledProcessError as exc:
            raise AssertionError("Failed to create virtualenv") from exc
        return self

    def __exit__(self, *_: Any) -> None:
        """
        Exit the context manager.
        """
        shutil.rmtree(str(self.venv_dir), ignore_errors=True)

    def install(self, *args: str, **kwargs: Any) -> ProcessResult:
        """
        Install a python package into the virtualenv.
        """
        return self.run(self.venv_python, "-m", "pip", "install", *args, **kwargs)

    def run(self, *args: str, **kwargs: Any) -> ProcessResult:
        """
        Run a shell command.
        """
        check = kwargs.pop("check", True)
        kwargs.setdefault("cwd", str(self.cwd or self.venv_dir))
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)
        kwargs.setdefault("universal_newlines", True)
        kwargs.setdefault("env", self.environ)
        proc = subprocess.run(args, check=False, **kwargs)
        ret = ProcessResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmdline=proc.args,
        )
        log.debug(ret)
        if check is True:
            try:
                proc.check_returncode()
            except subprocess.CalledProcessError as exc:  # pragma: no cover
                raise ProcessFailed("Command failed return code check", process_result=ret) from exc
        return ret

    @staticmethod
    def get_real_python() -> str:
        """
        Return the path to the real python executable.

        The reason why the virtualenv creation is proxied by this function is mostly
        because under windows, we can't seem to properly create a virtualenv off of
        another virtualenv(we can on Linux) and also because, we really don't want to
        test virtualenv creation off of another virtualenv, we want a virtualenv created
        from the original python.
        Also, on windows, we must also point to the virtualenv binary outside the existing
        virtualenv because it will fail otherwise
        """
        # sys.real_prefix is set by virtualenv
        try:
            if platform.is_windows():
                return os.path.join(sys.real_prefix, os.path.basename(sys.executable))  # type: ignore[attr-defined]
            else:
                python_binary_names = [
                    "python{}.{}".format(*sys.version_info),
                    "python{}".format(*sys.version_info),
                    "python",
                ]
                for binary_name in python_binary_names:
                    python = os.path.join(sys.real_prefix, "bin", binary_name)  # type: ignore[attr-defined]
                    if os.path.exists(python):
                        break
                else:
                    raise AssertionError(
                        "Couldn't find a python binary name under '{}' matching: {}".format(
                            os.path.join(sys.real_prefix, "bin"), python_binary_names  # type: ignore[attr-defined]
                        )
                    )
                return python
        except AttributeError:
            return sys.executable

    def run_code(self, code_string: str, **kwargs: Any) -> ProcessResult:
        """
        Run python code using the virtualenv python environment.

        Arguments:
            code_string:
                The code string to run against the virtualenv python interpreter

        Returns:
            ProcessResult: A ``ProcessResult`` instance for the executed code run.
        """
        if code_string.startswith("\n"):
            code_string = code_string[1:]
        code_string = textwrap.dedent(code_string).rstrip()
        log.debug("Code to run passed to python:\n>>>>>>>>>>\n%s\n<<<<<<<<<<", code_string)
        return self.run(str(self.venv_python), "-c", code_string, **kwargs)

    def get_installed_packages(self) -> Dict[str, str]:
        """
        Return installed packages in the virtualenv.

        Get a dictionary of the installed packages where the keys are the package
        names and the values their versions
        """
        data: Dict[str, str] = {}
        ret = self.run(str(self.venv_python), "-m", "pip", "list", "--format", "json")
        for pkginfo in json.loads(ret.stdout):
            data[pkginfo["name"]] = pkginfo["version"]
        return data

    def _create_virtualenv(self) -> None:
        args = [
            self.get_real_python(),
            "-m",
            "virtualenv",
        ]
        passed_python = False
        for arg in self.venv_create_args:
            if arg.startswith(("--python", "--python=")):
                passed_python = True
            args.append(arg)
        if passed_python is False:
            args.append(f"--python={self.get_real_python()}")
        args.append(str(self.venv_dir))
        # We pass CWD because run defaults to the venv_dir, which, at this stage
        # is not yet created
        self.run(*args, cwd=os.getcwd())
        self.install("-U", "pip", "setuptools!=50.*,!=51.*,!=52.*")
        log.debug("Created virtualenv in %s", self.venv_dir)
