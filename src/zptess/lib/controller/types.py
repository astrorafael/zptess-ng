

from typing import Tuple, Mapping

from lica import StrEnum
from lica.asyncio.photometer import Role


# Round Statistics type. 
# [0] =frequence, [1] = freq std dev, [2] magnitude according to ficticios ZP
FreqStatistics = Tuple[float, float, float]
RoundStatsType = Mapping[Role, FreqStatistics]

class Event(StrEnum):
	READING = "reading_event"
	ROUND = "round_event"

