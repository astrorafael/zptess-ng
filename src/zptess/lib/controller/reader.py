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

from typing import Any, Mapping


# ---------------------------
# Third-party library imports
# ----------------------------

from lica.sqlalchemy.asyncio.dbase import engine, AsyncSession
from lica.asyncio.photometer.builder import PhotometerBuilder
from lica.asyncio.photometer import Model as PhotModel, Sensor, Role

# --------------
# local imports
# -------------

from .base import Controller as BaseController
from .ring import RingBuffer

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


class Reader(BaseController):
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

    async def calibrate(self) -> float:
        """Calibrate the test photometer against the refrence photometer retirnoing a Zero Point"""
        raise NotImplementedError("Not relevant method for %s" % (self.__class__.__name__))

    async def write_zp(self, zero_point: float) -> float:
         raise NotImplementedError("Not relevant method for %s" % (self.__class__.__name__))

    async def init(self) -> None:
        log.info(
            "Initializing %s controller for %s",
            self.__class__.__name__,
            self.roles,
        )
        builder = PhotometerBuilder(engine)  # For the reference photometer using database info
        async with self.Session() as session:
            for role in self.roles:
                val_db = await self._load(session, SECTION[role], "model")
                val_arg = self.param[role]["model"]
                self.param[role]["model"] = val_arg if val_arg is not None else PhotModel(val_db)
                val_db = await self._load(session, SECTION[role], "sensor")
                val_arg = self.param[role]["sensor"]
                self.param[role]["sensor"] = val_arg if val_arg is not None else Sensor(val_db)
                val_db = await self._load(session, SECTION[role], "old-proto")
                val_arg = self.param[role]["old_proto"]
                self.param[role]["old_proto"] = val_arg if val_arg is not None else bool(val_db)
                val_db = await self._load(session, SECTION[role], "endpoint")
                val_arg = self.param[role]["endpoint"]
                self.param[role]["endpoint"] = val_arg if val_arg is not None else val_db
                self.photometer[role] = builder.build(self.param[role]["model"], role, self.param[role]["endpoint"])
                self.ring[role] = RingBuffer(capacity=1)
                self.task[role] = asyncio.create_task(self.photometer[role].readings())
                logging.getLogger(str(role)).setLevel(self.param[role]["log_level"])
