"""
Salt loader mock support for tests.
"""
from __future__ import generator_stop
import logging
import pytest
from saltfactories.utils.loader import LoaderModuleMock

log = logging.getLogger(__name__)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items):
    """
    Modify the collected items.

    Iterate through the collected items, in particular their test modules, to see if there's a function
    named ``configure_loader_modules``. If there is, assert that it's a fixture. If not, raise an error.
    """
    seen_modules = set()
    for item in items:
        if item.module.__name__ in seen_modules:
            continue
        seen_modules.add(item.module.__name__)
        typos = (
            'configure_loader_module',
            'configure_load_module',
            'configure_load_modules',
        )
        for typo in typos:
            try:
                fixture = getattr(item.module, typo)
                try:
                    fixture._pytestfixturefunction
                    raise RuntimeError(
                        "The module {} defines a '{}' fixture but the correct fixture name is 'configure_loader_modules'".format(
                            item.module, typo
                        )
                    )
                except AttributeError:
                    pass
            except AttributeError:
                pass
        try:
            fixture = item.module.configure_loader_modules
        except AttributeError:
            continue
        else:
            try:
                fixture._pytestfixturefunction
            except AttributeError:
                raise RuntimeError(
                    "The module {} defines a 'configure_loader_modules' function but that function is not a fixture".format(
                        item.module
                    )
                ) from None


@pytest.fixture(autouse=True)
def setup_loader_mock(request):
    """
    Setup Salt's loader mocking/patching if the test module defines a ``configure_loader_modules`` fixture.
    """
    try:
        request.node.module.configure_loader_modules
    except AttributeError:
        yield
    else:
        configure_loader_modules = request.getfixturevalue('configure_loader_modules')
        with LoaderModuleMock(configure_loader_modules) as loader_mock:
            yield loader_mock
