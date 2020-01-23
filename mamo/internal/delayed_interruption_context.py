import signal
from contextlib import contextmanager
from typing import Iterable, Optional


# Adapted from https://stackoverflow.com/a/21919644/854731
@contextmanager
def delayed_interruption():
    signal_received: Optional[Iterable] = None

    def handler(self, sig, frame):
        nonlocal signal_received
        signal_received = (sig, frame)

    old_handler = signal.signal(signal.SIGINT, handler)

    yield

    signal.signal(signal.SIGINT, old_handler)
    if signal_received:
        old_handler(*signal_received)

