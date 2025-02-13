# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging
from typing import Mapping, Any

# ---------------------------
# Third-party library imports
# ----------------------------


from lica.asyncio.photometer import Role

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


class Controller(BaseController):
    """
    Reader Controller specialized in reading the photometers
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

    async def write_zp(self, zero_point: float) -> float:
        raise NotImplementedError("Not relevant method for %s" % (self.__class__.__name__))

    async def init(self) -> None:
        await super().init()
        for role in self.roles:
            self.ring[role] = RingBuffer(capacity=1)
        await self._launch_phot_tasks()