# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

from abc import ABC, abstractmethod
import logging
import asyncio

from typing import  Dict, Tuple, AsyncIterator


# ---------------------------
# Third-party library imports
# ----------------------------

from sqlalchemy import select
from lica.asyncio.photometer import  Role, Message as PhotMessage

# --------------
# local imports
# -------------

from ...lib.dbase.model import Config

# ----------------
# Module constants
# ----------------


SECTION = {Role.REF: "ref-device", Role.TEST: "test-device"}

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


class Controller(ABC):
    """
    Reader Controller specialized in reading the photometers
    """

    def buffer(self, role: Role):
        return self.ring[role]

    async def _load(self, session, section: str, prop: str) -> str | None:
        async with session:
            q = select(Config.value).where(Config.section == section, Config.prop == prop)
            return (await session.scalars(q)).one_or_none()

    @abstractmethod
    async def init(self) -> None:
        pass

    @abstractmethod
    async def calibrate(self) -> float:
        """Calibrate the test photometer against the refrence photometer retirnoing a Zero Point"""
        pass

    async def info(self, role: Role) -> Dict[str, str]:
        log = logging.getLogger(role.tag())
        try:
            phot_info = await self.photometer[role].get_info()
        except asyncio.exceptions.TimeoutError:
            log.critical("Failed contacting %s photometer", role.tag())
            raise
        except Exception as e:
            log.critical(e)
            raise
        else:
            phot_info["endpoint"] = role.endpoint()
            phot_info["sensor"] = phot_info["sensor"] or self.param[role]["sensor"].value
            v = phot_info["freq_offset"] or 0.0
            phot_info["freq_offset"] = float(v)
            self.phot_info[role] = phot_info
            return phot_info

    async def receive(self, role: Role, num_messages: int | None = None) -> AsyncIterator[Tuple[Role,PhotMessage]]:
        """An asynchronous generator, to be used by clients with async for"""
        if num_messages is None:
            while True:
                msg = await self.photometer[role].queue.get()
                yield role, msg
        else:
            for i in range(num_messages):
                msg = await self.photometer[role].queue.get()
                yield role, msg

    async def write_zp(self, zero_point: float) -> float:
        """May raise asyncio.exceptions.TimeoutError in particular"""
        await self.photometer[Role.TEST].save_zero_point(zero_point)
        stored_zero_point = (await self.photometer[Role.TEST].get_info())["zp"]
        return stored_zero_point
