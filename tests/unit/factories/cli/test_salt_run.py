"""
Test the ``salt-run`` CLI functionality.
"""
import shutil
import sys
from pathlib import Path

import pytest
from _pytest.pytester import Pytester

from saltfactories.cli.run import SaltRun


@pytest.fixture
def config_dir(pytester: Pytester) -> Path:
    _conf_dir = pytester.mkdir("conf")
    try:
        yield _conf_dir
    finally:
        shutil.rmtree(str(_conf_dir), ignore_errors=True)


@pytest.fixture
def minion_id() -> str:
    return "test-minion-id"


@pytest.fixture
def config_file(config_dir: Path, minion_id: str) -> str:
    config_file = str(config_dir / "config")
    with open(config_file, "w") as wfh:
        wfh.write("id: {}\n".format(minion_id))
    return config_file


@pytest.fixture
def cli_script_name(pytester: Pytester) -> str:
    py_file = pytester.makepyfile(
        """
        print("This would be the CLI script")
        """
    )
    try:
        yield str(py_file)
    finally:
        py_file.unlink()


def test_default_timeout_config(
    minion_id: str, config_dir: Path, config_file: str, cli_script_name: str
) -> None:
    """
    Assert against the default timeout provided in the config.
    """
    with open(config_file, "a") as wfh:
        wfh.write("timeout: 15\n")
    config = {"conf_file": config_file, "id": minion_id, "timeout": 15}
    args = ["test.ping"]
    proc = SaltRun(script_name=cli_script_name, config=config)
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--timeout=15",
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
    ] + ["test.ping"]
    cmdline = proc.cmdline(*args)
    assert cmdline == expected


def test_default_timeout_construct(
    minion_id: str, config_dir: Path, config_file: str, cli_script_name: str
) -> None:
    """
    Assert against the default timeout provided in the config.
    """
    config = {"conf_file": config_file, "id": minion_id}
    args = ["test.ping"]
    proc = SaltRun(script_name=cli_script_name, config=config, timeout=15)
    expected = [
        sys.executable,
        cli_script_name,
        "--config-dir={}".format(config_dir),
        "--timeout=15",
        "--out=json",
        "--out-indent=0",
        "--log-level=critical",
    ] + ["test.ping"]
    cmdline = proc.cmdline(*args)
    assert cmdline == expected
