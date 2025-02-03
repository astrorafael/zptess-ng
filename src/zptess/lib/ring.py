# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import math
import logging
import statistics
import collections

# -------------------
# Third party imports
# -------------------


# --------------
# local imports
# -------------

from . import CentralTendency

# ----------------
# Module constants
# ----------------

# -----------------------
# Module global variables
# -----------------------

# get the root logger
log = logging.getLogger(__name__.split(".")[-1])

# -------
# Classes
# -------


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

    def __len__(self):
        return len(self._buffer)

    def capacity(self):
        return self._buffer.maxlen
        
    def pop(self):
        return self._buffer.popleft()

    def append(self, item):
        self._buffer.append(item)

    def frequencies(self):
        return [item["freq"] for item in self._buffer]

    def statistics(self):
        frequencies = tuple(item["freq"] for item in self._buffer)
        central = self._central_func(frequencies)
        stdev = statistics.stdev(frequencies, central)
        return central, stdev
