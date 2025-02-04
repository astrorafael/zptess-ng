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

from typing import Any, Mapping, Dict


# ---------------------------
# Third-party library imports
# ----------------------------

from pubsub import pub

from sqlalchemy import select

from lica.sqlalchemy.asyncio.dbase import engine, AsyncSession
from lica.asyncio.photometer.builder import PhotometerBuilder
from lica.asyncio.photometer import Model as PhotModel, Sensor, Role

# --------------
# local imports
# -------------

from .ring import RingBuffer
from ...lib.dbase.model import Config

# ----------------
# Module constants
# ----------------


SECTION1 = {Role.REF: "ref-device", Role.TEST: "test-device"}

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


class Reader:
    """
    Reader Controller specialized in reading the photometers
    """

    def __init__(
        self,
        ref_params: Mapping[str, Any] | None = None,
        test_params: Mapping[str, Any] | None = None,
    ):
        self.Session = AsyncSession
        self.param = {Role.REF: ref_params, Role.TEST: test_params}
        self.photometer = dict()
        self.ring = dict()
        self.phot_info = dict()
        self.roles = list()
        self.task = dict()
        if ref_params is not None:
            self.roles.append(Role.REF)
        if test_params is not None:
            self.roles.append(Role.TEST)

    def buffer(self, role: Role):
        return self.ring[role]

    async def _load(self, session, section: str, prop: str) -> str | None:
        async with session:
            q = select(Config.value).where(Config.section == section, Config.prop == prop)
            return (await session.scalars(q)).one_or_none()

    async def init(self) -> None:
        log.info(
            "Initializing %s controller for %s",
            self.__class__.__name__,
            self.roles,
        )
        builder = PhotometerBuilder(engine)  # For the reference photometer using database info
        async with self.Session() as session:
            for role in self.roles:
                val_db = await self._load(session, SECTION1[role], "model")
                val_arg = self.param[role]["model"]
                self.param[role]["model"] = val_arg if val_arg is not None else PhotModel(val_db)
                val_db = await self._load(session, SECTION1[role], "sensor")
                val_arg = self.param[role]["sensor"]
                self.param[role]["sensor"] = val_arg if val_arg is not None else Sensor(val_db)
                val_db = await self._load(session, SECTION1[role], "old-proto")
                val_arg = self.param[role]["old_proto"]
                self.param[role]["old_proto"] = val_arg if val_arg is not None else bool(val_db)
                val_db = await self._load(session, SECTION1[role], "endpoint")
                val_arg = self.param[role]["endpoint"]
                self.param[role]["endpoint"] = val_arg if val_arg is not None else val_db
                self.photometer[role] = builder.build(self.param[role]["model"], role)
                self.ring[role] = RingBuffer(capacity=1)
                self.task[role] = asyncio.create_task(self.photometer[role].readings())
                logging.getLogger(str(role)).setLevel(self.param[role]["log_level"])

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

    async def fill_buffer(self, role: Role) -> None:
        while True:
            msg = await self.photometer[role].queue.get()
            self.ring[role].append(msg)
            pub.sendMessage("reading_info", controller=self, role=role, reading=msg)

    async def receive(self) -> None:
        coros = [self.fill_buffer(role) for role in self.roles]
        await asyncio.gather(*coros)
