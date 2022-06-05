"""
Salt Factories PyTest plugin interface.
"""
from __future__ import generator_stop
import logging
import os
import tempfile
from typing import Any
import pytest
import pytestskipmarkers.utils.platform
from _pytest.reports import TestReport
import saltfactories.utils.tempfiles

log = logging.getLogger(__name__)


def pytest_tempdir_temproot() -> str:
    """
    Define the temp directory to use as a base for the test run.
    """
    if pytestskipmarkers.utils.platform.is_windows():
        tempdir = 'C:/Windows/Temp'
    elif pytestskipmarkers.utils.platform.is_darwin():
        tempdir = '/tmp'
    else:
        tempdir = os.environ.get('TMPDIR') or tempfile.gettempdir()
    return os.path.abspath(os.path.realpath(tempdir))


def pytest_tempdir_basename() -> str:
    """
    Return the temporary directory basename for the salt test suite.
    """
    return 'saltfactories'


def pytest_runtest_logstart(nodeid: str) -> None:
    """
    Signal the start of running a single test item.

    This hook will be called **before** :func:`pytest_runtest_setup`, :func:`pytest_runtest_call` and
    :func:`pytest_runtest_teardown` hooks.

    :param str nodeid: full id of the item
    :param location: a triple of ``(filename, linenum, testname)``
    """
    log.debug('>>>>>>> START %s >>>>>>>', nodeid)


def pytest_runtest_logfinish(nodeid: str) -> None:
    """
    Signal the complete finish of running a single test item.

    This hook will be called **after** :func:`pytest_runtest_setup`, :func:`pytest_runtest_call` and
    :func:`pytest_runtest_teardown` hooks.

    :param str nodeid: full id of the item
    :param location: a triple of ``(filename, linenum, testname)``
    """
    log.debug('<<<<<<< END %s <<<<<<<', nodeid)


def pytest_runtest_logreport(report: TestReport) -> None:
    """
    Log the test running.

    Process the :py:class:`_pytest.reports.TestReport` produced for each
    of the setup, call and teardown runtest phases of an item.
    See :func:`pytest_runtest_protocol` for a description of the runtest protocol.
    """
    if report.when == 'call':
        log.debug('======= %s %s ========', report.outcome.upper(), report.nodeid)


@pytest.hookimpl(trylast=True)
def pytest_load_initial_conftests(*_: Any) -> None:
    """
    Register our pytest helpers.
    """
    if 'temp_directory' not in pytest.helpers:
        pytest.helpers.register(
            saltfactories.utils.tempfiles.temp_directory, name='temp_directory'
        )
    if 'temp_file' not in pytest.helpers:
        pytest.helpers.register(
            saltfactories.utils.tempfiles.temp_file, name='temp_file'
        )
