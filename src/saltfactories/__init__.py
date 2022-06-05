import importlib.abc
import pathlib
import re
import sys
from types import ModuleType
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

USE_DOWNGRADED_TRANSPILED_CODE = sys.version_info < (3, 7)


if USE_DOWNGRADED_TRANSPILED_CODE:
    # We generated downgraded code just for Py<3.7
    # Let's just import from those modules instead

    class NoTypingImporter(importlib.abc.SourceLoader):
        """
        Meta importer to redirect imports on Py<3.7.
        """

        NO_REDIRECT_NAMES = (
            "saltfactories.version",
            "saltfactories.downgraded",
        )

        def find_module(  # noqa: D102
            self, module_name: str, package_path: Optional[str] = None
        ) -> Optional["NoTypingImporter"]:
            if module_name.startswith(self.NO_REDIRECT_NAMES):
                return None
            if not module_name.startswith("saltfactories"):
                return None
            return self

        def load_module(self, name: str) -> ModuleType:  # noqa: D102
            if not name.startswith(self.NO_REDIRECT_NAMES):
                mod = importlib.import_module("saltfactories.downgraded.{}".format(name[14:]))
            else:
                mod = importlib.import_module(name)
            sys.modules[name] = mod
            return mod

        def get_data(self, path: Union[str, bytes]) -> bytes:
            """
            Reads path as a binary file and returns the bytes from it.
            """
            return pathlib.Path(str(path)).read_bytes()

        def get_filename(self, fullname: str) -> str:
            """
            Return the filename matching the fullname.
            """
            if not fullname.startswith(self.NO_REDIRECT_NAMES):
                fullname = "saltfactories.downgraded.{}".format(fullname[14:])
            path_parts = fullname.split(".")
            filename = path_parts.pop()  # grab the file name or dirname
            path_parts.pop(0)  # drop saltfactories
            path = pathlib.Path(__file__).parent
            if path_parts:
                path = path.joinpath(*path_parts)
            if path.joinpath(filename).is_dir():
                path = path / filename / "__init__.py"
            else:
                path = path / "{}.py".format(filename)
            return str(path)

    # Try our importer first
    sys.meta_path = [NoTypingImporter()] + sys.meta_path  # type: ignore[assignment,operator]


try:
    from .version import __version__
except ImportError:  # pragma: no cover
    __version__ = "0.0.0.not-installed"
    try:
        from importlib.metadata import version, PackageNotFoundError

        try:
            __version__ = version("pytest-salt-factories")
        except PackageNotFoundError:
            # package is not installed
            pass
    except ImportError:
        try:
            from importlib_metadata import version, PackageNotFoundError

            try:
                __version__ = version("pytest-salt-factories")
            except PackageNotFoundError:
                # package is not installed
                pass
        except ImportError:
            try:
                from pkg_resources import get_distribution, DistributionNotFound

                try:
                    __version__ = get_distribution("pytest-salt-factories").version
                except DistributionNotFound:
                    # package is not installed
                    pass
            except ImportError:
                # pkg resources isn't even available?!
                pass


# Define __version_info__ attribute
VERSION_INFO_REGEX = re.compile(
    r"(?P<major>[\d]+)\.(?P<minor>[\d]+)\.(?P<patch>[\d]+)"
    r"(?:\.dev(?P<commits>[\d]+)\+g(?P<sha>[a-z0-9]+)\.d(?P<date>[\d]+))?"
)
try:
    _match = VERSION_INFO_REGEX.match(__version__)
    if _match is not None:
        __version_info__ = tuple(int(p) if p.isdigit() else p for p in _match.groups() if p)
        del _match
    else:  # pragma: no cover
        __version_info__ = (-1, -1, -1)
finally:
    del VERSION_INFO_REGEX


# Define some constants
CODE_ROOT_DIR = pathlib.Path(__file__).resolve().parent
IS_WINDOWS = sys.platform.startswith("win")
IS_DARWIN = IS_OSX = sys.platform.startswith("darwin")
