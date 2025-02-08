# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging
import asyncio

from typing import Any, Mapping, Sequence


# ---------------------------
# Third-party library imports
# ----------------------------

from pubsub import pub
from lica.asyncio.photometer import Role

# --------------
# local imports
# -------------

from .volatile import Controller as VolatileCalibrator
from .types import Event, RoundStatsType

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


class Controller(VolatileCalibrator):
    """
    Reader Controller specialized in reading the photometers
    """

    def __init__(
        self,
        ref_params: Mapping[str, Any] | None = None,
        test_params: Mapping[str, Any] | None = None,
        common_params: Mapping[str, Any] | None = None,
    ):
        super().__init__(ref_params, test_params, common_params)
        self.db_queue = asyncio.Queue()
        pub.subscribe(self.on_round, Event.ROUND)
        pub.subscribe(self.on_summary, Event.SUMMARY)

    async def init(self) -> None:
        await super().init()
        self.db_task = asyncio.create_task(self.db_writer())

    async def db_writer(self) -> None:
        while True:
            msg = await self.db_queue.get()
            log.info(msg)

    def on_round(
        self, current: int, mag_diff: float, zero_point: float, stats: RoundStatsType
    ) -> None:
        msg = {
            "event": Event.ROUND,
            "payload": {
                "current": current,
                "mag_diff": mag_diff,
                "zero_point": zero_point,
                "stats": stats,
            },
        }
        self.db_queue.put_nowait(msg)

    def on_summary(
        self,
        zero_point_seq: Sequence[float],
        ref_freq_seq: Sequence[float],
        test_freq_seq: Sequence[float],
        best_ref_freq: float,
        best_ref_mag: float,
        best_test_freq: float,
        best_test_mag: float,
        mag_diff: float,
        best_zero_point: float,
        final_zero_point: float,
    ) -> None:
        msg = {
            "event": Event.SUMMARY,
            "payload": {
                "zero_point_seq": zero_point_seq,
                "ref_freq_seq": ref_freq_seq,
                "test_freq_seq": test_freq_seq,
                "best_ref_freq": best_ref_freq,
                "best_ref_mag": best_ref_mag,
                "best_test_freq": best_test_freq,
                "best_test_mag": best_test_mag,
                "mag_diff": mag_diff,
                "best_zero_point": best_zero_point,
                "final_zero_point": final_zero_point,
            },
        }
        self.db_queue.put_nowait(msg)
