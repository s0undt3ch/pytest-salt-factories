"""
``salt-call`` CLI factory.
"""
from __future__ import generator_stop
import attr
from saltfactories.bases import SaltCli


@attr.s(kw_only=True, slots=True)
class SaltCall(SaltCli):
    """
    ``salt-call`` CLI factory.
    """

    __cli_timeout_supported__ = attr.ib(repr=False, init=False, default=True)

    def get_minion_tgt(self, minion_tgt=None):
        """
        Overridden method because salt-run does not target minions, it runs locally.
        """
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        """
        Process the returned output.
        """
        self._minion_tgt = 'local'
        return super().process_output(stdout, stderr, cmdline=cmdline)
