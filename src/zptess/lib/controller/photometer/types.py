

from typing import Tuple, Sequence, Mapping

from lica import StrEnum
from lica.asyncio.photometer import Role


# Per-Role Round Statistics type. 
# Tuple[0] =frequency, 
# Tuple[1] = freq std dev, 
# Tuple[2] magnitude according to ficticios ZP
RoundStatistics = Tuple[float, float, float]

# Summary statictis
# Tuple[0]: sequence of zero points, 
# Tuple[1]: sequence of reference central frequencies
# Tuple[2]: sequence of test central frecuencies
SummaryStatistics = Tuple[Sequence[float], Sequence[float], Sequence[float]]

RoundStatsType = Mapping[Role, RoundStatistics]


class Event(StrEnum):
	READING = "reading_event"
	ROUND = "round_event"
	SUMMARY = "summary_event"
	CAL_START = "calib_start_event"
	CAL_END = "calib_end_event"

