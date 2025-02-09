# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------
from __future__ import annotations

import logging
import asyncio
from abc import ABC, abstractmethod

from typing import Any, Mapping


# ---------------------------
# Third-party library imports
# ----------------------------

from pubsub import pub
from lica.asyncio.photometer import Role

# --------------
# local imports
# -------------

from .volatile import Controller as VolatileCalibrator
from .types import Event

# ----------------
# Module constants
# ----------------

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
    Database-based Photometer Calibration Controller
    """

    def __init__(
        self,
        ref_params: Mapping[str, Any] | None = None,
        test_params: Mapping[str, Any] | None = None,
        common_params: Mapping[str, Any] | None = None,
    ):
        super().__init__(ref_params, test_params, common_params)
        self.db_queue = asyncio.Queue()
        self._state = None

    def transition_to(self, state: State):
        """
        The Context allows changing the State object at runtime.
        """
        log.info("Transition to %s", type(state).__name__)
        self._state = state
        self._state.controller = self

    async def init(self) -> None:
        await super().init()
        self.transition_to(StartState())
        self.db_task = asyncio.create_task(self.db_writer())

    async def db_writer(self) -> None:
        self.calibrating = True
        while self.calibrating:
            msg = await self.db_queue.get()
            event = msg["event"]
            if event == Event.CAL_START:
                self._state.handle_start()
            elif event == Event.ROUND:
                self._state.handle_round(msg["info"], msg["samples"])
            elif event == Event.SUMMARY:
                self._state.handle_summary(msg["info"])
            else:
                await self._state.handle_end()
        log.info("Database listener ends here")

    def on_calib_start(self) -> None:
        pub.sendMessage(Event.CAL_START)
        msg = {"event": Event.CAL_START, "info": None}
        self.db_queue.put_nowait(msg)

    def on_calib_end(self) -> None:
        pub.sendMessage(Event.CAL_END)
        msg = {"event": Event.CAL_END, "info": None}
        self.db_queue.put_nowait(msg)

    def on_round(self, round_info: Mapping[str, Any]) -> None:
        pub.sendMessage(Event.ROUND, **round_info)
        # We must copy the sequence of samples of a given round
        # since the background filling tasks are active
        msg = {
            "event": Event.ROUND,
            "info": round_info,
            "samples": {
                Role.REF: self.ring[Role.REF].copy(),
                Role.TEST: self.ring[Role.TEST].copy(),
            },
        }
        self.db_queue.put_nowait(msg)

    def on_summary(self, summary_info: Mapping[str, Any]) -> None:
        pub.sendMessage(Event.SUMMARY, **summary_info)
        msg = {"event": Event.SUMMARY, "info": summary_info}
        self.db_queue.put_nowait(msg)


class State(ABC):
    """
    The base State class declares methods that all Concrete State should
    implement and also provides a backreference to the Context object,
    associated with the State. This backreference can be used by States to
    transition the Context to another State.
    """

    _ctrl = None

    @property
    def controller(self) -> Controller:
        return self._ctrl

    @controller.setter
    def controller(self, ctrl: Controller) -> None:
        self._ctrl = ctrl

    @abstractmethod
    def handle_start(self) -> None:
        pass

    @abstractmethod
    async def handle_end(self) -> None:
        pass

    @abstractmethod
    def handle_round(self, round_info: Mapping[str, Any], samples: Mapping[str, Any]) -> None:
        pass

    @abstractmethod
    def handle_summary(self, round_info: Mapping[str, Any]) -> None:
        pass


class StartState(State):
    def handle_start(self) -> None:
        log.info("%s.%s()", self.__class__.__name__, self.handle_start.__name__)
        self.controller.transition_to(RoundState())

    async def handle_end(self) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_end.__name__)

    def handle_round(self, round_info: Mapping[str, Any], samples: Mapping[str, Any]) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_round.__name__)

    def handle_summary(self, round_info: Mapping[str, Any]) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_summary.__name__)


class RoundState(State):
    def handle_start(self) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_start.__name__)

    async def handle_end(self) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_end.__name__)

    def handle_round(self, round_info: Mapping[str, Any], samples: Mapping[str, Any]) -> None:
        log.info("%s.%s()", self.__class__.__name__, self.handle_round.__name__)
        if round_info["current"] == self.controller.nrounds:
            self.controller.transition_to(SummaryState())

    def handle_summary(self, round_info: Mapping[str, Any]) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_summary.__name__)


class SummaryState(State):
    def handle_start(self) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_start.__name__)

    async def handle_end(self) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_end.__name__)

    def handle_round(self, round_info: Mapping[str, Any], samples: Mapping[str, Any]) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_round.__name__)

    def handle_summary(self, round_info: Mapping[str, Any]) -> None:
        log.info("%s.%s()", self.__class__.__name__, self.handle_summary.__name__)
        self.controller.transition_to(EndState())


class EndState(State):
    def handle_start(self) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_start.__name__)

    def handle_round(self, round_info: Mapping[str, Any]) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_round.__name__)

    def handle_summary(self, round_info: Mapping[str, Any], samples: Mapping[str, Any]) -> None:
        log.warn("Ignoring %s.%s", self.__class__.__name__, self.handle_summary.__name__)

    async def handle_end(self) -> None:
        log.info("%s.%s()", self.__class__.__name__, self.handle_end.__name__)
        await asyncio.sleep(4)
        self.controller.calibrating = False
        log.info("Ending Database Calibration Process")
