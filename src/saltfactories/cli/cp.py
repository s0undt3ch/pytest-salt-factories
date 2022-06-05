"""
``salt-cp`` CLI factory.
"""
from __future__ import annotations

import attr

from saltfactories.bases import SaltCli


@attr.s(kw_only=True, slots=True)
class SaltCp(SaltCli):
    """
    salt-cp CLI factory.
    """

    __cli_timeout_supported__ = attr.ib(repr=False, init=False, default=True)

    def _get_default_timeout(self):
        return self.config.get("timeout")

    def process_output(self, stdout, stderr, cmdline=None):
        """
        Process the returned output.
        """
        if "No minions matched the target. No command was sent, no jid was assigned.\n" in stdout:
            stdout = stdout.split("\n", 1)[1:][0]
        return super().process_output(stdout, stderr, cmdline=cmdline)
