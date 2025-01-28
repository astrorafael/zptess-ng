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

from typing import Mapping, Dict, Iterable

# ---------------------------
# Third-party library imports
# ----------------------------

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionClass
from sqlalchemy.ext.asyncio import async_sessionmaker

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

    def __init__(self, which: Iterable[str], 
        models: Mapping[Role, PhotModel], sensors: Mapping[Role, Sensor], 
        buffered: bool = False, query: bool = False):
        self.Session = AsyncSession
        self.photometer = [None, None]
        self.producer = [None, None]
        self.consumer = [None, None]
        self.ring = [None, None]
        self.cur_mac = [None, None]
        self.which = which
        self.sensor = [None, None]
        self.model = [None, None]
        self.role = [None,None]
        self.buffered = buffered
        self.query = query
        if "ref" in self.which:
            self.sensor[Role.REF] = sensors[Role.REF]
            self.model[Role.REF] = models[Role.REF]
            self.role[Role.REF] = Role.REF
        if "test" in self.which:
            self.sensor[Role.TEST] = sensors[Role.TEST]
            self.model[Role.TEST] = models[Role.TEST]
            self.role[Role.TEST] = Role.TEST

    async def init(self) -> None:
        log.info("Initializing %s controller for %s (buffered=%s)", self.__class__.__name__, self.which, self.buffered)
        builder = PhotometerBuilder(engine) # For the reference photometer using database info
        async with self.Session() as session:
            if "ref" in self.which:
                self.photometer[Role.REF] =  builder.build(self.model[Role.REF], Role.REF)
                if self.buffered:
                    q = select(Config.value).where(Config.section == 'ref-stats', Config.prop == 'samples')
                    ring_buffer_size = int((await session.scalars(q)).one_or_none())
                    self.ring[Role.REF] = RingBuffer(ring_buffer_size)
            if "test" in self.which:
                self.photometer[Role.TEST] =  builder.build(self.model[Role.TEST], Role.TEST)
                if self.buffered:
                    q = select(Config.value).where(Config.section == 'test-stats', Config.prop == 'samples')
                    ring_buffer_size = int((await session.scalars(q)).one_or_none())
                    self.ring[Role.TEST] = RingBuffer(ring_buffer_size)
       
    async def info(self, role: Role) -> Dict[str,str]:
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
            return phot_info


    async def start(self) -> None:
        if "ref" in self.which:
            phot_info = await self.info(Role.REF)
            log = logging.getLogger(Role.REF.tag())
            for key, value in sorted(phot_info.items()):
                log.info("%-12s: %s", key.upper(), value)
        if "test" in self.which:
            phot_info = await self.info(Role.TEST)
            log = logging.getLogger(Role.TEST.tag())
            for key, value in sorted(phot_info.items()):
                log.info("%-12s: %s", key.upper(), value)
        if self.query:
            return

