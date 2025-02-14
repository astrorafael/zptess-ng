# ----------------------------------------------------------------------
# Copyright (c) 2024 Rafael Gonzalez.
#
# See the LICENSE file for details
# ----------------------------------------------------------------------


# --------------------
# System wide imports
# -------------------

import sys
import logging

from typing import Optional, List, Set
from datetime import datetime

# =====================
# Third party libraries
# =====================


if sys.version_info[1] < 11:
    from typing_extensions import Self
else:
    from typing import Self


from sqlalchemy import (
    select,
    func,
    Enum,
    Table,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lica.sqlalchemy.asyncio.dbase import Model
from lica.sqlalchemy.view import view
from lica.asyncio.photometer import Model as PhotModel, Role, Sensor

from .. import CentralTendency, Calibration

# ================
# Module constants
# ================

# =======================
# Module global variables
# =======================

# get the module logger
log = logging.getLogger(__name__)


def datestr(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f") if dt is not None else None


# =================================
# Data Model, declarative ORM style
# =================================

# ---------------------------------------------
# Additional conveniente types for enumerations
# ---------------------------------------------

RoleType: Enum = Enum(
    Role,
    name="role_type",
    create_constraint=False,
    metadata=Model.metadata,
    validate_strings=True,
    values_callable=lambda x: [e.name.lower() for e in x],
)

PhotModelType: Enum = Enum(
    PhotModel,
    name="model_type",
    create_constraint=False,
    metadata=Model.metadata,
    validate_strings=True,
    values_callable=lambda x: [e.value for e in x],
)


SensorType: Enum = Enum(
    Sensor,
    name="sensor_type",
    create_constraint=False,
    metadata=Model.metadata,
    validate_strings=True,
    values_callable=lambda x: [e.value for e in x],
)

CentralTendencyType: Enum = Enum(
    CentralTendency,
    name="central_type",
    create_constraint=False,
    metadata=Model.metadata,
    validate_strings=True,
    values_callable=lambda x: [e.value for e in x],
)

CalibrationType: Enum = Enum(
    Calibration,
    name="calibration_type",
    create_constraint=False,
    metadata=Model.metadata,
    validate_strings=True,
    values_callable=lambda x: [e.value for e in x],
)

# --------
# Entities
# --------


class Config(Model):
    __tablename__ = "config_t"

    section: Mapped[str] = mapped_column(String(32), primary_key=True)
    prop: Mapped[str] = mapped_column("property", String(255), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))

    def __repr__(self) -> str:
        return f"Config(section={self.section!r}, prop={self.prop!r}, value={self.value!r})"


class Batch(Model):
    __tablename__ = "batch_t"

    begin_tstamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    end_tstamp: Mapped[Optional[datetime]] = mapped_column(DateTime)
    email_sent: Mapped[Optional[bool]]
    calibrations: Mapped[Optional[int]]
    comment: Mapped[Optional[str]] = mapped_column(String(255))

    def __repr__(self) -> str:
        return f"Batch(begin={datestr(self.begin_tstamp)}, end={datestr(self.end_tstamp)}, N={self.calibrations!r}, emailed={self.email_sent!r})"


class Photometer(Model):
    __tablename__ = "photometer_t"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(10))
    mac: Mapped[str] = mapped_column(String(17))
    sensor: Mapped[SensorType] = mapped_column(SensorType, default=Sensor.TSL237)
    freq_offset: Mapped[float]
    model: Mapped[PhotModelType] = mapped_column(PhotModelType)
    firmware: Mapped[Optional[str]] = mapped_column(String(17))
    filter: Mapped[Optional[str]] = mapped_column(String(32), default="UV/IR-740")
    plug: Mapped[Optional[str]] = mapped_column(String(16), default="USB-A")
    box: Mapped[Optional[str]] = mapped_column(String(16), default="FSH714")
    collector: Mapped[Optional[str]] = mapped_column(
        String(16), default="standard"
    )  #  Collector model
    comment: Mapped[Optional[str]] = mapped_column(String(255))  # Photometer level comment

    # This is not a real column, it s meant for the ORM
    calibrations: Mapped[List["Summary"]] = relationship(back_populates="photometer")

    def __repr__(self) -> str:
        return f"Photom(id={self.id!r}, name={self.name!r}, mac={self.mac!r})"

    __table_args__ = (
        UniqueConstraint(name, mac),
        {},
    )


class Summary(Model):
    __tablename__ = "summary_t"

    id: Mapped[int] = mapped_column(primary_key=True)
    phot_id: Mapped[int] = mapped_column(ForeignKey("photometer_t.id"), index=True)
    session: Mapped[datetime] = mapped_column(DateTime)  # calibration session identifier
    role: Mapped[RoleType] = mapped_column(RoleType)
    calibration: Mapped[CalibrationType] = mapped_column(CalibrationType, nullable=True)
    calversion: Mapped[Optional[str]] = mapped_column(String(64))  # calibration software version
    author: Mapped[Optional[str]]  # who run the calibration
    nrounds: Mapped[Optional[int]]  # Number of rounds passed
    zp_offset: Mapped[
        Optional[float]
    ]  # Additional offset that was summed to the computed zero_point
    upd_flag: Mapped[Optional[bool]]  # 1 => TESS-W ZP was updated, 0 => TESS-W ZP was not updated
    prev_zp: Mapped[Optional[float]]
    zero_point: Mapped[Optional[float]]  #  calibrated zero point
    zero_point_method: Mapped[CentralTendencyType] = mapped_column(
        CentralTendencyType, nullable=True
    )
    freq: Mapped[Optional[float]]  # final chosen frequency
    freq_method: Mapped[CentralTendencyType] = mapped_column(CentralTendencyType, nullable=True)
    mag: Mapped[Optional[float]]
    comment: Mapped[Optional[str]] = mapped_column(
        String(512)
    )  #  Additional comment for the calibration process

    # These are not a real columns, it is meant for the ORM
    photometer: Mapped["Photometer"] = relationship(back_populates="calibrations")
    rounds: Mapped[List["Round"]] = relationship(back_populates="summary")
    samples: Mapped[Set["Sample"]] = relationship(back_populates="summary")

    def __repr__(self) -> str:
        return f"Summary(session={datestr(self.session)}, role={self.role!r}, phot_id={self.phot_id!r})"

    __table_args__ = (UniqueConstraint(session, role), {})


# Samples per round
# Due to the sliding window collect process, a sample may belong to several rounds
# This part is not part of the ORM, as it uses the basic Table API
SamplesRounds = Table(
    "samples_rounds_t",
    Model.metadata,
    Column("round_id", ForeignKey("rounds_t.id"), nullable=False, primary_key=True),
    Column("sample_id", ForeignKey("samples_t.id"), nullable=False, primary_key=True),
)


class Round(Model):
    __tablename__ = "rounds_t"

    id: Mapped[int] = mapped_column(primary_key=True)
    summ_id: Mapped[int] = mapped_column(ForeignKey("summary_t.id"), index=True)
    seq: Mapped[int] = mapped_column("round", Integer)  # Round number form 1..NRounds
    role: Mapped[RoleType] = mapped_column(RoleType)
    # session:    Mapped[datetime] = mapped_column(DateTime)
    freq: Mapped[Optional[float]]
    # Either average or median of samples for this frequencies round
    central: Mapped[CentralTendencyType] = mapped_column(CentralTendencyType, nullable=True)
    stddev: Mapped[Optional[float]]  # Standard deviation for frequency central estimate
    mag: Mapped[
        Optional[float]
    ]  # magnitiude corresponding to central frequency and summing ficticious zero point
    zp_fict: Mapped[Optional[float]]  # Ficticious ZP to estimate instrumental magnitudes (=20.50)
    zero_point: Mapped[
        Optional[float]
    ]  # Estimated Zero Point for this round ('test' photometer round only, else NULL)
    nsamples: Mapped[Optional[int]]  # Number of samples for this round
    duration: Mapped[Optional[float]]  # Approximate duration, in seconds
    begin_tstamp: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_tstamp: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # This is not a real column, it s meant for the ORM
    summary: Mapped["Summary"] = relationship(back_populates="rounds")
    # samples per round. Shoudl match the window size
    # This is not a real column, it s meant for the ORM
    samples: Mapped[List["Sample"]] = relationship(secondary=SamplesRounds, back_populates="rounds")

    def __repr__(self) -> str:
        return f"Round(id={self.id!r}, #{self.seq!r} [{self.nsamples!r}] {self.role!r}, zp={self.zero_point} f={self.freq}, m={self.mag:.2f}@{self.zp_fict} Ts={datestr(self.begin_tstamp)}, Te={datestr(self.end_tstamp)})"

    __table_args__ = (UniqueConstraint(summ_id, seq, role), {})


class Sample(Model):
    __tablename__ = "samples_t"

    id: Mapped[int] = mapped_column(primary_key=True)
    summ_id: Mapped[int] = mapped_column(ForeignKey("summary_t.id"), index=True)
    tstamp: Mapped[datetime] = mapped_column(DateTime)
    role: Mapped[RoleType] = mapped_column(RoleType)
    seq: Mapped[Optional[int]]
    freq: Mapped[float]
    temp_box: Mapped[Optional[float]]

    # rounds per sample (at least 1...)
    # This is not a real column, it s meant for the ORM
    rounds: Mapped[List["Round"]] = relationship(secondary=SamplesRounds, back_populates="samples")

    # This is not a real column, it s meant for the ORM
    summary: Mapped["Summary"] = relationship(back_populates="samples")

    def __repr__(self) -> str:
        return f"Sample(id={self.id!r}, role={self.role!r} freq={self.freq!r},  seq={self.seq!r})"

    def __lt__(self, other: Self) -> bool:
        return self.tstamp < other.tstamp

    def __le__(self, other: Self) -> bool:
        return self.tstamp <= other.tstamp

    def __eq__(self, other: Self) -> bool:
        return self.tstamp == other.tstamp

    def __ne__(self, other: Self) -> bool:
        return self.tstamp != other.tstamp

    def __gt__(self, other: Self) -> bool:
        return self.tstamp > other.tstamp

    def __ge__(self, other: Self) -> bool:
        return self.tstamp >= other.tstamp

    def __hash__(self):
        return hash(self.tstamp)

    __table_args__ = (UniqueConstraint(tstamp, role), {})


# Create the view for barebones SQL statements from console
summary_view = view(
    name="summary_v",
    metadata=Model.metadata,
    selectable=select(
        Summary.__table__.c.id.label("id"),
        Photometer.__table__.c.name.label("name"),
        Photometer.__table__.c.mac.label("mac"),
        Summary.__table__.c.session.label("session"),
        Summary.__table__.c.role.label("role"),
        Summary.__table__.c.nrounds.label("nrounds"),
        Summary.__table__.c.upd_flag.label("upd_flag"),
        func.round(Summary.__table__.c.zero_point, 2).label("zero_point"),
        func.round(Summary.__table__.c.zp_offset, 2).label("zp_offset"),
        func.round((Summary.__table__.c.zero_point - Summary.__table__.c.zp_offset), 2).label(
            "raw_zero_point"
        ),
        Summary.__table__.c.calibration.label("calibration"),
        func.round(Summary.__table__.c.prev_zp, 2).label("prev_zp"),
        func.round(Summary.__table__.c.freq, 3).label("freq"),
        func.round(Summary.__table__.c.mag, 2).label("mag"),
        Summary.__table__.c.zero_point_method.label("zero_point_method"),
        Summary.__table__.c.freq_method.label("freq_method"),
        Summary.__table__.c.calversion.label("calversion"),
        Summary.__table__.c.comment.label("comment"),
    )
    .select_from(Summary.__table__.join(Photometer.__table__))
    .where(Summary.__table__.c.role == Role.TEST),
)

# Another view for debugging data
rounds_view = view(
    name="rounds_v",
    metadata=Model.metadata,
    selectable=select(
        Round.__table__.c.id.label("id"),
        Photometer.__table__.c.name.label("name"),
        Photometer.__table__.c.mac.label("mac"),
        Photometer.__table__.c.model.label("model"),
        Summary.__table__.c.session.label("session"),
        Round.__table__.c.round.label("round"),
        Round.__table__.c.role.label("role"),
        Round.__table__.c.freq.label("freq"),
        Round.__table__.c.central.label("central"),
        Round.__table__.c.stddev.label("stddev"),
        Round.__table__.c.mag.label("mag"),
        Round.__table__.c.zp_fict.label("zp_fict"),
        Round.__table__.c.zero_point.label("zero_point"),
        Round.__table__.c.nsamples.label("nsamples"),
        Round.__table__.c.duration.label("duration"),
        Round.__table__.c.begin_tstamp.label("begin_tstamp"),
        Round.__table__.c.end_tstamp.label("end_tstamp"),
        Summary.__table__.c.upd_flag.label("upd_flag"),
        Summary.__table__.c.nrounds.label("nrounds"),
        Summary.__table__.c.freq.label("mean_freq"),
        Summary.__table__.c.freq_method.label("freq_method"),
    )
    .select_from(Round.__table__.join(Summary.__table__))
    .join(Photometer.__table__),
)


class SummaryView(Model):
    __table__ = summary_view

    def __repr__(self) -> str:
        return f"SummaryView(name={self.name}, mac={self.mac}, session={datestr(self.session)}, role={self.role!r}, nrounds={self.nrounds!r}, zp={self.zero_point!r}, calib={self.calibration!r}, freq={self.freq!r})"
