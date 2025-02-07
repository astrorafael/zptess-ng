# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging

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

from .ring import RingBuffer
from .base import Controller as BaseController


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


class Controller(BaseController):
    """
    Writer Controller specialized in writing Zero Points via API
    """

    def __init__(
        self,
        ref_params: Mapping[str, Any] | None = None,
        test_params: Mapping[str, Any] | None = None,
    ):
        super().__init__(ref_params, test_params)

    async def calibrate(self) -> float:
        """Calibrate the test photometer against the refrence photometer retirnoing a Zero Point"""
        raise NotImplementedError("Not relevant method for %s" % (self.__class__.__name__))

    async def init(self) -> None:
        await super().init()
        for role in self.roles:
            self.ring[role] = RingBuffer(capacity=1)
