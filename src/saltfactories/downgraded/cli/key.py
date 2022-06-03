"""
``salt-key`` CLI factory.

..
    PYTEST_DONT_REWRITE
"""
from __future__ import generator_stop
import re
import attr
from salt.utils.parsers import SaltKeyOptionParser
from saltfactories.bases import SaltCli

try:
    SALT_KEY_LOG_LEVEL_SUPPORTED = (
        SaltKeyOptionParser._skip_console_logging_config_ is False
    )
except AttributeError:
    try:
        SALT_KEY_LOG_LEVEL_SUPPORTED = (
            '--log-level' in SaltKeyOptionParser._console_log_level_cli_flags
        )
    except AttributeError:
        SALT_KEY_LOG_LEVEL_SUPPORTED = True


@attr.s(kw_only=True, slots=True)
class SaltKey(SaltCli):
    """
    salt-key CLI factory.
    """

    _output_replace_re = attr.ib(
        init=False,
        repr=False,
        default=re.compile(
            '((The following keys are going to be.*:|Key for minion.*)\\n)'
        ),
    )
    __cli_log_level_supported__ = attr.ib(
        repr=False, init=False, default=SALT_KEY_LOG_LEVEL_SUPPORTED
    )

    def get_minion_tgt(self, minion_tgt=None):
        """
        Overridden method because salt-key does not target minions.
        """
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        """
        Process the returned output.
        """
        stdout = self._output_replace_re.sub('', stdout)
        return super().process_output(stdout, stderr, cmdline=cmdline)
