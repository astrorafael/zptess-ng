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
import asyncio
from collections import defaultdict

from typing import Any, Mapping



# ---------------------------
# Third-party library imports
# ----------------------------

import statistics

from pubsub import pub
from lica.asyncio.photometer import  Role

# --------------
# local imports
# -------------

from .ring import RingBuffer
from .reader import Reader

from .. import CentralTendency

# ----------------
# Module constants
# ----------------

SECTION2 = {Role.REF: "ref-stats", Role.TEST: "test-stats"}

# -----------------------
# Module global variables
# -----------------------

# get the module logger
log = logging.getLogger(__name__.split(".")[-1])

# -------------------
# Auxiliary functions
# -------------------

# -----------------
# Auxiliary classes
# -----------------


class Calibrator(Reader):
    """
    Reader Controller specialized in reading the photometers
    """

    def __init__(
        self,
        ref_params: Mapping[str, Any] | None = None,
        test_params: Mapping[str, Any] | None = None,
        common_params: Mapping[str, Any] | None = None,
    ):
        super().__init__(ref_params, test_params)
        self.common_param = common_params
        self.period = None
        self.central = None
        self.nrounds = None
        self.zp_fict = None
        self.zp_offset = None
        self.zp_abs = None
        self.author = None

    async def init(self) -> None:
        await super().init()
        async with self.Session() as session:
            val_db = await self._load(session, SECTION2[Role.TEST], "samples")
            val_arg = self.common_param["buffer"]
            self.capacity = val_arg if val_arg is not None else int(val_db)
            val_db = await self._load(session, SECTION2[Role.TEST], "period")
            val_arg = self.common_param["period"]
            self.period = val_arg if val_arg is not None else float(val_db)
            val_db = await self._load(session, SECTION2[Role.TEST], "central")
            val_arg = self.common_param["central"]
            self.central = val_arg if val_arg is not None else CentralTendency(val_db)
            val_db = await self._load(session, "calibration", "zp_fict")
            val_arg = self.common_param["zp_fict"]
            self.zp_fict = val_arg if val_arg is not None else float(val_db)
            val_db = await self._load(session, "calibration", "rounds")
            val_arg = self.common_param["rounds"]
            self.nrounds = val_arg if val_arg is not None else int(val_db)
            val_db = await self._load(session, "calibration", "offset")
            val_arg = self.common_param["zp_offset"]
            self.zp_offset = val_arg if val_arg is not None else float(val_db)
            val_db = await self._load(session, "calibration", "author")
            val_arg = self.common_param["author"]
            self.author = val_arg if val_arg is not None else val_db
            # The absolute ZP is the stored ZP in the reference photometer.
            self.zp_abs =  float(await self._load(session, "ref-device", "zp"))
        self.dry_run = self.common_param["dry_run"]
        self.update = self.common_param["update"]
        self.ring[Role.REF] = RingBuffer(capacity=self.capacity, central=self.central)
        self.ring[Role.TEST] = RingBuffer(capacity=self.capacity, central=self.central)

    async def producer_task(self, role: Role) -> None:
        while not self.is_calibrated:
            msg = await self.photometer[role].queue.get()
            self.ring[role].append(msg)

    async def fill_buffer(self, role: Role) -> None:
        while len(self.ring[role]) < self.capacity:
            msg = await self.photometer[role].queue.get()
            self.ring[role].append(msg)
            pub.sendMessage("reading_info", role=role, reading=msg)

    def magnitude(self, role: Role, freq: float, freq_offset):
        return self.zp_fict - 2.5 * math.log10(freq - freq_offset)

    def round_statistics(self, role: Role):
        log = logging.getLogger(role.tag())
        freq_offset = self.phot_info[role]["freq_offset"]
        freq = stdev = mag = None
        try:
            freq, stdev = self.ring[role].statistics()
            mag = self.magnitude(role, freq, freq_offset)
        except statistics.StatisticsError as e:
            log.error("Statistics error: %s", e)
        except ValueError as e:
            log.error("math.log10() error for freq=%s, freq_offset=%s}: %s", freq, freq_offset, e)
        finally: 
            return freq, stdev, mag

    async def statistics(self):
        for i in range(1, self.nrounds + 1):
            round_info = defaultdict(dict)
            for role in self.roles:
                round_info["stats"][role] = self.round_statistics(role)
                round_info["Ti"][role] = self.ring[role][0]['tstamp']
                round_info["Tf"][role] = self.ring[role][-1]['tstamp']
                round_info["T"][role] = (round_info["Tf"][role] - round_info["Ti"][role]).total_seconds()
                round_info["N"][role] = len(self.ring[role])
                round_info["central"][role] = self.central
                round_info["zp_fict"][role] = self.zp_fict
            round_info["delta_mag"] = round_info["stats"][Role.REF][2] - round_info["stats"][Role.TEST][2]
            round_info["zero_point"] = round(self.zp_abs + round_info["delta_mag"], 2)
            round_info["zp_abs"] = self.zp_abs
            pub.sendMessage("round_info", current=i, nrounds=self.nrounds, round_info=round_info, phot_info=self.phot_info)
            if i !=  self.nrounds:
                await asyncio.sleep(10)
        self.is_calibrated = True

    async def calibrate(self) -> None:
        coros = [self.fill_buffer(role) for role in self.roles]
        # Waiting for both circular buffers to be filled
        await asyncio.gather(*coros)
        self.producer = [None, None]
        # background task that fill the circular buffers while we perform
        # the calibratu¡ion rounds
        self.producer[Role.REF] = asyncio.create_task(self.producer_task(Role.REF))
        self.producer[Role.TEST] = asyncio.create_task(self.producer_task(Role.TEST))
        self.is_calibrated = False
        await asyncio.gather(self.statistics(), *self.producer)
