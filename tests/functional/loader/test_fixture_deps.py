from __future__ import annotations

import logging
from types import ModuleType
from typing import Any
from typing import Dict
from typing import Iterator
from unittest.mock import patch

import pytest

import saltfactories
from saltfactories.utils.loader import LoaderModuleMock

try:
    # pylint: disable=pointless-statement
    saltfactories.__salt__  # type: ignore[attr-defined]
    # pylint: enable=pointless-statement
    HAS_SALT_DUNDER = True
except AttributeError:
    HAS_SALT_DUNDER = False

log = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def confirm_saltfactories_does_not_have_salt_dunders() -> None:
    assert (
        HAS_SALT_DUNDER is False
    ), "Weirdly, the saltfactories module has a __salt__ dunder defined. That's a bug!"


def confirm_saltfactories_does_not_have_salt_dunders_after_setup_loader_mock_terminates(
    setup_loader_mock: Iterator[LoaderModuleMock],
) -> Iterator[None]:
    yield
    with pytest.raises(AttributeError):
        assert isinstance(saltfactories.__salt__, dict)  # type: ignore[attr-defined]


@pytest.fixture
def pre_loader_modules_patched_fixture() -> Iterator[bool]:
    with pytest.raises(AttributeError):
        assert isinstance(saltfactories.__salt__, dict)  # type: ignore[attr-defined]
    yield False


@pytest.fixture
def configure_loader_modules(
    pre_loader_modules_patched_fixture: bool,
) -> Dict[ModuleType, Dict[str, Any]]:
    return {
        saltfactories: {
            "__salt__": {"test.echo": lambda x: x, "foo": pre_loader_modules_patched_fixture}
        }
    }


@pytest.fixture
def fixture_that_needs_loader_modules_patched() -> Iterator[None]:
    assert saltfactories.__salt__["foo"] is False  # type: ignore[attr-defined]
    with patch.dict(saltfactories.__salt__, {"foo": True}):  # type: ignore[attr-defined]
        assert saltfactories.__salt__["foo"] is True  # type: ignore[attr-defined]
        yield
    assert saltfactories.__salt__["foo"] is False


def test_fixture_deps(fixture_that_needs_loader_modules_patched: None) -> None:
    assert saltfactories.__salt__["foo"] is True  # type: ignore[attr-defined]
    assert saltfactories.__salt__["test.echo"]("foo") == "foo"  # type: ignore[attr-defined]
