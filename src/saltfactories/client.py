"""
Salt Client in-process implementation.

..
    PYTEST_DONT_REWRITE
"""
from __future__ import annotations

import logging
import re
from typing import Any
from typing import Dict
from typing import List
from typing import Pattern
from typing import Tuple
from typing import Union

import attr
import pytest
import salt.client


log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class LocalClient:
    """
    Wrapper class around Salt's local client.
    """

    STATE_FUNCTION_RUNNING_RE: Pattern[str] = re.compile(
        r"""The function (?:"|')(?P<state_func>.*)(?:"|') is running as PID """
        r"(?P<pid>[\d]+) and was started at (?P<date>.*) with jid (?P<jid>[\d]+)"
    )

    master_config: Dict[str, Any] = attr.ib(repr=False)
    functions_known_to_return_none: Union[List[str], Tuple[str, ...]] = attr.ib(repr=False)
    __client: salt.client.LocalClient = attr.ib(init=False, repr=False)

    @functions_known_to_return_none.default
    def _set_functions_known_to_return_none(self) -> Tuple[str, ...]:
        return (
            "data.get",
            "file.chown",
            "file.chgrp",
            "pkg.refresh_db",
            "ssh.recv_known_host_entries",
            "time.sleep",
        )

    @__client.default
    def _set_client(self) -> salt.client.LocalClient:
        return salt.client.get_local_client(mopts=self.master_config)

    def run(
        self,
        function: str,
        *args: Any,
        minion_tgt: str = "minion",
        timeout: int = 300,
        **kwargs: Any,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Run a single salt function.

        Additional condition the return down to match the behavior of the raw function call.
        """
        if "f_arg" in kwargs:
            kwargs["arg"] = kwargs.pop("f_arg")
        if "f_timeout" in kwargs:
            kwargs["timeout"] = kwargs.pop("f_timeout")
        ret: Dict[str, Union[List[Dict[str, Any]], Dict[str, Any]]] = self.__client.cmd(
            minion_tgt, function, args, timeout=timeout, kwarg=kwargs
        )
        if minion_tgt not in ret:
            pytest.fail(
                "WARNING(SHOULD NOT HAPPEN #1935): Failed to get a reply "
                "from the minion '{}'. Command output: {}".format(minion_tgt, ret)
            )
        elif ret[minion_tgt] is None and function not in self.functions_known_to_return_none:
            pytest.fail(
                "WARNING(SHOULD NOT HAPPEN #1935): Failed to get '{}' from "
                "the minion '{}'. Command output: {}".format(function, minion_tgt, ret)
            )

        # Try to match stalled state functions
        ret[minion_tgt] = self._check_state_return(ret[minion_tgt])

        return ret[minion_tgt]

    def _check_state_return(
        self, ret: Union[List[Dict[str, Any]], Dict[str, Any]]
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        if isinstance(ret, dict):
            # This is the supposed return format for state calls
            return ret

        if isinstance(ret, list):
            jids: List[str] = []
            # These are usually errors
            for item in ret[:]:
                if not isinstance(item, str):
                    # We don't know how to handle this
                    continue
                match = self.STATE_FUNCTION_RUNNING_RE.match(item)
                if not match:
                    # We don't know how to handle this
                    continue
                jid = match.group("jid")
                if jid in jids:
                    continue

                jids.append(jid)
                job_data = self.run("saltutil.find_job", jid)
                job_kill = self.run("saltutil.kill_job", jid)

                msg = (
                    "A running state.single was found causing a state lock. "
                    "Job details: '{}'  Killing Job Returned: '{}'".format(job_data, job_kill)
                )
                ret.append(f"[TEST SUITE ENFORCED]{msg}[/TEST SUITE ENFORCED]")
        return ret
