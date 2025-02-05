# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------

# --------------------
# System wide imports
# -------------------

import logging

# -------------------
# Third party imports
# -------------------

from lica.asyncio.photometer import Role

# --------------
# local imports
# -------------

from ...lib.controller import Controller


async def log_phot_info(controller: Controller, role: Role) -> None:
    log = logging.getLogger(role.tag())
    phot_info = await controller.info(role)
    log.info("-" * 40)
    for key, value in sorted(phot_info.items()):
        log.info("%-12s: %s", key.upper(), value)
    log.info("-" * 40)


async def log_messages(controller: Controller, role: Role, num: int | None = None) -> None:
    log = logging.getLogger(role.tag())
    name = controller.phot_info[role]["name"]
    async for role, msg in controller.receive(role, num):
        log.info(
            "%-9s [%d] f=%s Hz, tbox=%s, tsky=%s",
            name,
            msg.get("seq"),
            msg["freq"],
            msg["tamb"],
            msg["tsky"],
        )
