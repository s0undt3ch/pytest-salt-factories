from __future__ import generator_stop

try:
    import coverage

    coverage.process_startup()
except ImportError:
    pass
