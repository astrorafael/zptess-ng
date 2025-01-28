# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging

from typing import Mapping, Iterable

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

    def __init__(self, which: Iterable[str], models: Mapping[Role, PhotModel], sensors: Mapping[Role, Sensor], buffered: bool = False):
        self.Session = AsyncSession
        self.photometer = [None, None]
        self.producer = [None, None]
        self.consumer = [None, None]
        self.ring = [None, None]
        self.cur_mac = [None, None]
        self.which = which
        self.sensor = [None, None]
        self.model = [None, None]
        self.buffered = buffered
        if "ref" in self.which:
            self.sensor[Role.REF] = sensors[Role.REF]
            self.model[Role.REF] = models[Role.REF]
        if "test" in self.which:
            self.sensor[Role.TEST] = sensors[Role.TEST]
            self.model[Role.TEST] = models[Role.TEST]

    async def start(self) -> None:
        log.info("loading configuration data")
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
       


