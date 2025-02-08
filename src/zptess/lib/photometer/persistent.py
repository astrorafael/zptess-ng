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

    async def init(self) -> None:
        await super().init()
        self.db_task = asyncio.create_task(self.db_writer())

    async def db_writer(self) -> None:
        while True:
            msg = await self.db_queue.get()
            log.info(msg)

    def on_round(self, round_info: Mapping[str, Any]) -> None:
        pub.sendMessage(Event.ROUND, **round_info)
        msg = {
            "event": Event.ROUND,
            "payload": round_info
        }
        self.db_queue.put_nowait(msg)

    def on_summary(self, summary_info: Mapping[str, Any]) -> None:
        pub.sendMessage(Event.SUMMARY, **summary_info)
        msg = {
            "event": Event.SUMMARY,
            "payload": summary_info
        }
        self.db_queue.put_nowait(msg)
