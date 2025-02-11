# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging
import statistics
import collections
from typing import Tuple, Mapping, Sequence, Any

# -------------------
# Third party imports
# -------------------


# --------------
# local imports
# -------------

from .. import CentralTendency

# ----------------
# Module constants
# ----------------

Message = Mapping[str, Any]

# -----------------------
# Module global variables
# -----------------------

# get the root logger
log = logging.getLogger(__name__.split(".")[-1])

# -------
# Classes
# -------
# This meant for easy sample de-duplication
# which are usually shared between rounds

class UniqueReading(dict):
    """A hashable, subclaased dictionary based on the "tstamp" keyword and value"""

    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)

    def __getitem__(self, key):
        return dict.__getitem__(self, key)

    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)

    def __repr__(self):
        return "%s(%s)" % (type(self).__name__, dict.__repr__(self))

    def __hash__(self):
        return int(dict.__getitem__(self, "tstamp").timestamp() * 1000)

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v



class RingBuffer:
    def __init__(
        self,
        capacity: int = 75,
        central: CentralTendency = CentralTendency.MEDIAN,
    ):
        self._buffer = collections.deque([], capacity)
        self._central = central
        if central == CentralTendency.MEDIAN:
            self._central_func = statistics.median_low
        elif central == CentralTendency.MEAN:
            self._central_func = statistics.fmean
        elif central == CentralTendency.MODE:
            self._central_func = statistics.mode

    def __len__(self) -> int:
        return len(self._buffer)

    def __getitem__(self, i: int) -> Message:
        return self._buffer[i]

    def capacity(self) -> int:
        return self._buffer.maxlen

    def pop(self) -> Message:
        return self._buffer.popleft()

    def append(self, item: Message) -> None:
        self._buffer.append(item)

    def copy(self) -> Sequence[Message]:
        return tuple(UniqueReading(item) for item in self._buffer)

    def statistics(self) -> Tuple[float, float]:
        frequencies = tuple(item["freq"] for item in self._buffer)
        central = self._central_func(frequencies)
        stdev = statistics.stdev(frequencies, central)
        return central, stdev
