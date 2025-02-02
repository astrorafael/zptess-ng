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

from typing import Mapping, Dict, Tuple, List, Generator


# ---------------------------
# Third-party library imports
# ----------------------------

from pubsub import pub

from typing_extensions import Self

from sqlalchemy import select

from lica.sqlalchemy.asyncio.dbase import engine, AsyncSession
from lica.asyncio.photometer.builder import PhotometerBuilder
from lica.asyncio.photometer import Model as PhotModel, Sensor, Role

# --------------
# local imports
# -------------

from .ring import RingBuffer
from ..lib.dbase.model import Config

# ----------------
# Module constants
# ----------------

PhotResult = Generator[Tuple[str, List[float], int], Tuple[Self, Role], None]


SECTION = {Role.REF: "ref-device", Role.TEST: "test-device"}
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


class Reader:
    """
    Reader Controller specialized in reading the photometers
    with or without ring buffer
    """

    def __init__(
        self,
        models: Mapping[Role, PhotModel],
        sensors: Mapping[Role, Sensor],
        endpoint: Mapping[Role, str],
        old_proto: Mapping[Role, bool],
        buffered: bool = False,
    ):
        self.Session = AsyncSession
        self.photometer = dict()
        self.producer = dict()
        self.consumer = dict()
        self.ring = dict()
        self.cur_mac = dict()
        self.phot_info = dict()
        self.sensor = sensors
        self.model = models
        self.old_proto = old_proto
        self.endpoint = endpoint
        self.buffered = buffered


    def buffer(self, role: Role):
        return self.ring[role]
    

    async def _load(self, session, section: str, prop: str) -> str | None:
        async with session:
            q = select(Config.value).where(Config.section == section, Config.prop == prop)
            return (await session.scalars(q)).one_or_none()

    async def init(self) -> None:
        log.info(
            "Initializing %s controller for %s (buffered=%s)",
            self.__class__.__name__,
            [k for k in self.model.keys()],
            self.buffered,
        )
        builder = PhotometerBuilder(engine)  # For the reference photometer using database info
        roles = sorted(self.model.keys())

        async with self.Session() as session:
            for role in roles:
                v = await self._load(session, SECTION[role], "model")
                self.model[role] = self.model[role] or PhotModel(v)
                v = await self._load(session, SECTION[role], "sensor")
                self.sensor[role] = self.sensor[role] or Sensor(v)
                v = await self._load(session, SECTION[role], "old-proto")
                self.old_proto[role] = self.old_proto[role] or bool(v)
                v = await self._load(session, SECTION[role], "endpoint")
                self.endpoint[role] = self.endpoint[role] or v
                self.photometer[role] = builder.build(self.model[role], role)
                if self.buffered:
                    capacity = int(await self._load(session, SECTION2[role], "samples"))
                else:
                    capacity = 1
                self.ring[role] = RingBuffer(capacity)
                self.producer[role] = asyncio.create_task(self.photometer[role].readings())

    async def info(self, role: Role) -> Dict[str, str]:
        log = logging.getLogger(role.tag())
        try:
            phot_info = await self.photometer[role].get_info()
        except asyncio.exceptions.TimeoutError:
            txt = f"Failed contacting {role.tag()} photometer"
            log.error(txt)
            return {"error_messg": txt}
        except Exception as e:
            log.error(e)
            txt = f"{e}"
            return {"err_msg": txt}
        else:
            phot_info["endpoint"] = role.endpoint()
            phot_info["sensor"] = phot_info["sensor"] or self.sensor[role].value
            phot_info["freq_offset"] = phot_info["freq_offset"] or 0.0
            self.phot_info[role] = phot_info
            return phot_info


    async def _receive(self, role: Role) -> None:
        while True:
            msg = await self.photometer[role].queue.get()
            self.ring[role].append(msg)
            pub.sendMessage('reading_info', controller=self, role=role, reading=msg)

         

    async def receive(self) -> None:
        coros = [self._receive(role) for role in sorted(self.photometer.keys())]
        await asyncio.gather(*coros)
