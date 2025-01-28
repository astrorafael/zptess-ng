# ----------------------------------------------------------------------
# Copyright (c) 2022
#
# See the LICENSE file for details
# see the AUTHORS file for authors
# ----------------------------------------------------------------------

# ---------------------
# Third party libraries
# ---------------------

import enum


class CentralTendency(enum.Enum):
    MEDIAN = "median"
    MODE = "mode"
    MEAN = "mean"

    def __repr__(self):
        return self.value
    def __str__(self):
        return self.value


class Calibration(enum.Enum):
    MANUAL = "MANUAL"
    AUTO = "AUTO"

    def __repr__(self):
        return self.value
    def __str__(self):
        return self.value


SERIAL_PORT_PREFIX = "/dev/ttyUSB"

# TESS-W data

TEST_IP    = '192.168.4.1'
TEST_TCP_PORT = 23
TEST_UDP_PORT = 2255
TEST_SERIAL_PORT = 0
TEST_BAUD = 9600

# Timestamp format
TSTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

# Condensed timestamp
TSTAMP_SESSION_FMT = '%Y-%m-%dT%H:%M:%S'
