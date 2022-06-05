"""
Salt External Logging Handler.
"""
from __future__ import generator_stop
import copy
import logging
import os
import pprint
import socket
import sys
import time
import traceback
from typing import Any
from typing import cast
from typing import Dict
from typing import Optional
from typing import Tuple
from typing import TYPE_CHECKING
from typing import Union

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict
try:
    from salt.utils.stringutils import to_unicode
except ImportError:
    from salt.utils import to_unicode
try:
    from salt._logging.impl import LOG_LEVELS
    from salt._logging.mixins import ExcInfoOnLogLevelFormatMixin
except ImportError:
    from salt.log.setup import LOG_LEVELS
    from salt.log.mixins import (
        ExcInfoOnLogLevelFormatMixIn as ExcInfoOnLogLevelFormatMixin,
    )
try:
    import msgpack

    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False
try:
    import zmq

    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False
if TYPE_CHECKING:
    __opts__ = None
__virtualname__ = 'pytest_log_handler'
log = logging.getLogger(__name__)


class LogConfig(TypedDict):
    host = None
    level = None
    port = None
    prefix = None
    disabled = None
    pytest_windows_guest = None


def __virtual__() -> Union[Tuple[bool, str], bool]:
    if HAS_MSGPACK is False:
        return False, 'msgpack was not importable. Please install msgpack.'
    if HAS_ZMQ is False:
        return False, 'zmq was not importable. Please install pyzmq.'
    if '__role' not in __opts__:
        return (
            False,
            "The required '__role' key could not be found in the options dictionary",
        )
    role = __opts__['__role']
    pytest_key = 'pytest-{0}'.format(role)
    if pytest_key not in __opts__ and 'pytest' not in __opts__:
        return (
            False,
            "Neither '{0}' nor 'pytest' keys in opts dictionary".format(pytest_key),
        )
    if pytest_key not in __opts__:
        pytest_key = 'pytest'
    pytest_config = __opts__[pytest_key]
    if 'log' not in pytest_config:
        return False, "No 'log' key in opts {0} dictionary".format(pytest_key)
    log_opts = pytest_config['log']
    if 'port' not in log_opts:
        return (
            False,
            "No 'port' key in opts['pytest']['log'] or opts['pytest'][{}]['log']".format(
                __opts__['role']
            ),
        )
    return True


def setup_handlers() -> Optional['ZMQHandler']:
    """
    Setup the handlers.
    """
    role = __opts__['__role']
    pytest_key = 'pytest-{0}'.format(role)
    pytest_config = __opts__[pytest_key]
    log_opts = pytest_config['log']
    if log_opts.get('disabled'):
        return None
    host_addr = log_opts.get('host')
    if not host_addr:
        import subprocess

        if log_opts['pytest_windows_guest'] is True:
            proc = subprocess.Popen(
                'ipconfig', stdout=subprocess.PIPE, universal_newlines=True
            )
            if TYPE_CHECKING:
                assert proc.stdout
            for line in proc.stdout.read().strip().splitlines():
                if 'Default Gateway' in line:
                    parts = line.split()
                    host_addr = parts[-1]
                    break
        else:
            proc = subprocess.Popen(
                "netstat -rn | grep -E '^0.0.0.0|default' | awk '{ print $2 }'",
                shell=True,
                stdout=subprocess.PIPE,
                universal_newlines=True,
            )
            if TYPE_CHECKING:
                assert proc.stdout
            host_addr = proc.stdout.read().strip()
    if TYPE_CHECKING:
        assert host_addr
    host_port = log_opts['port']
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host_addr, host_port))
    except OSError as exc:
        log.warning(
            'Cannot connect back to log server at %s:%d: %s', host_addr, host_port, exc
        )
        return None
    finally:
        sock.close()
    pytest_log_prefix = log_opts.get('prefix')
    try:
        level = LOG_LEVELS[(log_opts.get('level') or 'error').lower()]
    except KeyError:
        level = logging.ERROR
    handler = ZMQHandler(
        host=host_addr, port=host_port, log_prefix=pytest_log_prefix, level=level
    )
    handler.setLevel(level)
    handler.start()
    return handler


class ZMQHandler(ExcInfoOnLogLevelFormatMixin, logging.Handler):
    """
    ZMQ logging handler implementation.
    """

    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 3330,
        log_prefix: Optional[str] = None,
        level: int = logging.NOTSET,
        socket_hwm: int = 100000,
    ) -> None:
        super().__init__(level=level)
        self.host = host
        self.port = port
        self._log_prefix = log_prefix
        self.socket_hwm = socket_hwm
        self.log_prefix = self._get_log_prefix(log_prefix)
        self.context = self.pusher = None
        self._exiting = False
        self.dropped_messages_count = 0
        self.__formatter = logging.Formatter('%(message)s')
        self.pid = os.getpid()

    def _get_formatter(self) -> logging.Formatter:
        return self.__formatter

    def _set_formatter(self, fmt: Optional[logging.Formatter]) -> None:
        if fmt is not None:
            self.setFormatter(fmt)

    def _del_formatter(self) -> None:
        raise RuntimeError("Cannot delete the 'formatter' attribute")

    formatter = property(_get_formatter, _set_formatter, _del_formatter)

    def setFormatter(self, _: Optional[logging.Formatter]) -> None:
        """
        Overridden method to show an error.
        """
        raise RuntimeError(
            'Do not set a formatter on {0}'.format(self.__class__.__name__)
        )

    def __getstate__(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'port': self.port,
            'log_prefix': self._log_prefix,
            'level': self.level,
            'socket_hwm': self.socket_hwm,
        }

    def __setstate__(self, state: Dict[str, Any]) -> None:
        self.__init__(**state)
        self.stop()
        self._exiting = False

    def __repr__(self) -> str:
        return '<{} host={} port={} level={}>'.format(
            self.__class__.__name__,
            self.host,
            self.port,
            logging.getLevelName(self.level),
        )

    def _get_log_prefix(self, log_prefix: Optional[str] = None) -> Optional[str]:
        if log_prefix is None:
            return None
        if sys.argv[0] == sys.executable:
            cli_arg_idx = 1
        else:
            cli_arg_idx = 0
        cli_name = os.path.basename(sys.argv[cli_arg_idx])
        return log_prefix.format(cli_name=cli_name)

    def start(self) -> None:
        """
        Start the handler.
        """
        if self.pid != os.getpid():
            self.stop()
            self._exiting = False
        if self._exiting is True:
            return
        if self.pusher is not None:
            return
        self.dropped_messages_count = 0
        context = pusher = None
        try:
            context = zmq.Context()
            self.context = context
        except zmq.ZMQError as exc:
            sys.stderr.write(
                'Failed to create the ZMQ Context: {0}\n{1}\n'.format(
                    exc, traceback.format_exc()
                )
            )
            sys.stderr.flush()
            self.stop()
            self._exiting = False
            return
        try:
            pusher = context.socket(zmq.PUSH)
            pusher.set_hwm(self.socket_hwm)
            pusher.connect('tcp://{0}:{1}'.format(self.host, self.port))
            self.pusher = pusher
        except zmq.ZMQError as exc:
            if pusher is not None:
                pusher.close(0)
            sys.stderr.write(
                'Failed to connect the ZMQ PUSH socket: {}\n{}\n'.format(
                    exc, traceback.format_exc()
                )
            )
            sys.stderr.flush()
            self.stop()
            self._exiting = False
            return
        self.pid = os.getpid()

    def stop(self, flush: bool = True) -> None:
        """
        Stop the handler.
        """
        if self._exiting:
            return
        self._exiting = True
        if self.dropped_messages_count:
            sys.stderr.write(
                """Dropped {} messages from getting forwarded. High water mark reached...
""".format(
                    self.dropped_messages_count
                )
            )
            sys.stderr.flush()
        try:
            if self.pusher is not None and not self.pusher.closed:
                if flush:
                    linger = 1500
                else:
                    linger = 0
                self.pusher.close(linger)
                self.pusher = None
            if self.context is not None and not self.context.closed:
                self.context.term()
                self.context = None
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as exc:
            sys.stderr.write(
                'Failed to terminate ZMQHandler: {0}\n{1}\n'.format(
                    exc, traceback.format_exc()
                )
            )
            sys.stderr.flush()
            raise
        finally:
            if self.pusher is not None and not self.pusher.closed:
                self.pusher.close(0)
                self.pusher = None
            if self.context is not None and not self.context.closed:
                self.context.term()
                self.context = None
            self.pid = None

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record.
        """
        msg = super().format(record)
        if self.log_prefix:
            msg = '[{0}] {1}'.format(to_unicode(self.log_prefix), to_unicode(msg))
        return msg

    def prepare(self, record: logging.LogRecord) -> Optional[bytes]:
        """
        Prepare the log record.
        """
        msg = self.format(record)
        record = copy.copy(record)
        record.msg = msg
        record.args = None
        record.exc_info = None
        record.exc_text = None
        record.message = None
        record.stack_info = None
        try:
            return cast(bytes, msgpack.dumps(record.__dict__, use_bin_type=True))
        except TypeError as exc:
            sys.stderr.write(
                'Failed to serialize log record:{}.\n{}\nLog Record:\n{}\n'.format(
                    exc, traceback.format_exc(), pprint.pformat(record.__dict__)
                )
            )
            sys.stderr.flush()
            self.handleError(record)
        return None

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a record.

        Writes the LogRecord to the queue, preparing it for pickling first.
        """
        if self._exiting:
            return
        self.start()
        if self.pusher is None:
            sys.stderr.write(
                """Not sending log message over the wire because we were unable to connect to the log server.
"""
            )
            sys.stderr.flush()
            return
        try:
            msg = self.prepare(record)
            if msg:
                try:
                    self._send_message(msg)
                except zmq.error.Again:
                    time.sleep(0.001)
                    try:
                        self._send_message(msg)
                    except zmq.error.Again:
                        self.dropped_messages_count += 1
        except (SystemExit, KeyboardInterrupt):
            self.stop(flush=False)
            raise
        except Exception:
            self.handleError(record)

    def _send_message(self, msg: bytes) -> None:
        if TYPE_CHECKING:
            assert self.pusher
        self.pusher.send(msg, flags=zmq.NOBLOCK)
        if self.dropped_messages_count:
            logging.getLogger(__name__).debug(
                'Dropped %s messages from getting forwarded. High water mark reached...',
                self.dropped_messages_count,
            )
            self.dropped_messages_count = 0

    def close(self) -> None:
        """
        Tidy up any resources used by the handler.
        """
        self.stop(flush=False)
        self._exiting = True
        super().close()
