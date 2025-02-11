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
import contextlib

# -------------------
# Third party imports
# -------------------

from lica.asyncio.photometer import Role

# --------------
# local imports
# -------------

from ...lib.photometer import Controller


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
    # Although in this case, it doesn't matter, in general
    # async generatores may not close as expected,
    # hence the use of closing() context manager
    async with contextlib.aclosing(controller.receive(role, num)) as gen:
        async for role, msg in gen:
            log.info(
                "%-9s [%d] f=%s Hz, tbox=%s, tsky=%s",
                name,
                msg.get("seq"),
                msg["freq"],
                msg["tamb"],
                msg["tsky"],
            )


async def update_zp(controller: Controller, zero_point: float) -> None:
    log = logging.getLogger(Role.TEST.tag())
    zero_point = round(zero_point,2)
    log.info("Updating ZP : %0.2f", zero_point)
    name = controller.phot_info[Role.TEST]["name"]
    try:
        stored_zp = await controller.write_zp(zero_point)
    except asyncio.exceptions.TimeoutError:
        log.critical("[%s] Failed contacting %s photometer", name, Role.TEST.tag())
    except Exception as e:
        log.exception(e)
    else:
        if stored_zp is None:
            log.critical(
                "ZP Write verification failed: ZP to Write (%0.3f) "
                "doesn't match ZP subsequently read (%s). \u0394 = ?",
                zero_point,
                stored_zp,
            )
        elif stored_zp is None or zero_point != stored_zp:
            log.critical(
                "ZP Write verification failed: ZP to Write (%0.3f) "
                "doesn't match ZP subsequently read (%0.3f). \u0394 = %0.16f",
                zero_point,
                stored_zp,
                zero_point - stored_zp,
            )
        else:
            log.info("[%s] ZP Write (%0.2f) verification Ok.", name, zero_point)
