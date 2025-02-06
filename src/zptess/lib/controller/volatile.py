# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import math
import datetime
import logging
import asyncio

from typing import Any, Mapping, Sequence


# ---------------------------
# Third-party library imports
# ----------------------------

import statistics

from pubsub import pub
from lica.asyncio.photometer import Role

# --------------
# local imports
# -------------

from .types import Event, RoundStatistics, SummaryStatistics
from .ring import RingBuffer
from .reader import Controller as Reader


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


class Controller(Reader):
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
        self.meas_session = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
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
            self.zp_abs = float(await self._load(session, "ref-device", "zp"))
        self.persist = self.common_param["persist"]
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
            pub.sendMessage(Event.READING, role=role, reading=msg)

    def magnitude(self, role: Role, freq: float, freq_offset):
        return self.zp_fict - 2.5 * math.log10(freq - freq_offset)

    def round_statistics(self, role: Role) -> RoundStatistics:
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

    async def statistics(self) -> SummaryStatistics:
        zero_points = list()
        stats = list()
        for i in range(0, self.nrounds):
            stats_per_round = dict()
            for role in self.roles:
                stats_per_round[role] = self.round_statistics(role)
            delta_mag = stats_per_round[Role.REF][2] - stats_per_round[Role.TEST][2]
            zero_points.append(self.zp_abs + delta_mag)
            stats.append(stats_per_round)
            pub.sendMessage(
                Event.ROUND,
                current=i + 1,
                delta_mag=delta_mag,
                zero_point=zero_points[i],
                stats=stats_per_round,
            )
            if i != self.nrounds - 1:
                await asyncio.sleep(self.period)
        zero_points = [round(zp, 2) for zp in zero_points]
        ref_freqs = [stats_pr[Role.REF][0] for stats_pr in stats]
        test_freqs = [stats_pr[Role.TEST][0] for stats_pr in stats]
        self.is_calibrated = True # So no more buffer filling
        return zero_points, ref_freqs, test_freqs

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
        (zero_points, ref_freqs, test_freqs), _, _ = await asyncio.gather(
            self.statistics(), *self.producer
        )
        log.info(zero_points)
        log.info(ref_freqs)
        log.info(test_freqs)
        
