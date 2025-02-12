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
import statistics
from collections import defaultdict

from typing import Any, Mapping, Sequence

# ---------------------------
# Third-party library imports
# ----------------------------


from pubsub import pub
from lica.asyncio.photometer import Role

# --------------
# local imports
# -------------

from .util import best
from .types import Event, RoundStatistics, SummaryStatistics
from .ring import RingBuffer
from .base import Controller as BaseController


from .. import CentralTendency

# ----------------
# Module constants
# ----------------


SECTION = {Role.REF: "ref-stats", Role.TEST: "test-stats"}

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


class Controller(BaseController):
    """
    In-memory Photometer Calibration Controller
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
        self.accum_samples = defaultdict(list)
        self.time_intervals = defaultdict(list)

    async def init(self) -> None:
        await super().init()
        self.meas_session = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        async with self.Session() as session:
            val_db = await self._load(session, SECTION[Role.TEST], "samples")
            val_arg = self.common_param["buffer"]
            self.capacity = val_arg if val_arg is not None else int(val_db)
            val_db = await self._load(session, SECTION[Role.TEST], "period")
            val_arg = self.common_param["period"]
            self.period = val_arg if val_arg is not None else float(val_db)
            val_db = await self._load(session, SECTION[Role.TEST], "central")
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
        try:
                for role in self.roles:
                    self.ring[role] = RingBuffer(capacity=self.capacity, central=self.central)
                    self.task[role] = asyncio.create_task(self.photometer[role].readings())
        except* Exception as eg:
            for e in eg.exceptions:
                log.error(e)
            raise eg.exceptions[0]

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

    def on_calib_start(self) -> None:
        pub.sendMessage(Event.CAL_START)

    def on_calib_end(self) -> None:
        pub.sendMessage(Event.CAL_END)

    def on_round(self, round_info: Mapping[str, Any]) -> None:
        pub.sendMessage(Event.ROUND, **round_info)

    def on_summary(self, summary_info: Mapping[str, Any]) -> None:
        pub.sendMessage(Event.SUMMARY, **summary_info)

    async def not_updated(self, zero_point: float, msg: str):
        pass

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
        freqs = dict()
        for i in range(0, self.nrounds):
            stats_per_round = dict()
            for role in self.roles:
                stats_per_round[role] = self.round_statistics(role)
                self.accum_samples[role].append(self.ring[role].copy())
                self.time_intervals[role].append(self.ring[role].intervals()) 
            mag_diff = stats_per_round[Role.REF][2] - stats_per_round[Role.TEST][2]
            zero_points.append(self.zp_abs + mag_diff)
            stats.append(stats_per_round)
            round_info = {
                "current": i + 1,
                "mag_diff": mag_diff,
                "zero_point": zero_points[i],
                "stats": stats_per_round,
            }
            self.on_round(round_info)
            if i != self.nrounds - 1:
                await asyncio.sleep(self.period)
        zero_points = [round(zp, 2) for zp in zero_points]
        for role in self.roles:
            freqs[role] = [stats_pr[role][0] for stats_pr in stats]
        self.is_calibrated = True  # So no more buffer filling
        return zero_points, freqs

    def overlapping_windows(self) -> Mapping[Role, Sequence[float | None]]:
        overlaps = defaultdict(list)
        for role in self.roles:
            for i, t in enumerate(self.time_intervals[role]):
                if i < (self.nrounds - 1):
                    next_t = self.time_intervals[role][i + 1]
                    T = (t[1] - next_t[0]).total_seconds()
                    T = None if T <= 0 else T
                    overlaps[role].append(T)
        return overlaps

    def _post_statistics(self, zero_points, freqs) -> float:
        best_zp_method, best_zero_point = best(zero_points)
        best_freq = dict()
        best_freq_method = dict()
        best_mag = dict()
        for role in self.roles:
            best_freq_method[role], best_freq[role] = best(freqs[role])
            best_mag[role] = self.zp_fict - 2.5 * math.log10(best_freq[role])
        final_zero_point = best_zero_point + self.zp_offset
        mag_diff = -2.5 * math.log10(best_freq[Role.REF] / best_freq[Role.TEST])
        overlap = self.overlapping_windows()
        summary_info = {
            "zero_point_seq": zero_points,
            "freq_seq": freqs,
            "best_freq": best_freq,
            "best_freq_method": best_freq_method,
            "best_mag": best_mag,
            "mag_diff": mag_diff,
            "best_zero_point": best_zero_point,
            "best_zero_point_method": best_zp_method,
            "final_zero_point": final_zero_point,
            "overlapping_windows": overlap,
        }
        self.on_summary(summary_info)
        return final_zero_point

    async def calibrate(self) -> float:
        """
        Calibrate the Trst photometer against the Reference Photometer
        and return the final Zero Point to Write to the Test Photometer
        """
        self.on_calib_start()
        # Waiting for both circular buffers to be filled
        try:
            async with asyncio.TaskGroup() as tg:
                for role in self.roles:
                    tg.create_task(self.fill_buffer(role))
        except* Exception as eg:
            log.error(eg.exceptions)
        # launch the background buffer filling task and the stats task
        try:
            self.is_calibrated = False
            async with asyncio.TaskGroup() as tg:
                for role in self.roles:
                    tg.create_task(self.producer_task(role))
                stat_task = tg.create_task(self.statistics())
        except* Exception as eg:
            log.error(eg.exceptions)
        zero_points, freqs = stat_task.result()
        final_zero_point = self._post_statistics(zero_points, freqs)
        self.on_calib_end()
        return final_zero_point
