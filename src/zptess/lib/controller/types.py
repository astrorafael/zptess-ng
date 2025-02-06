

from typing import Tuple

from lica import StrEnum



# Round Statistics type. 
# [0] =frequence, [1] = freq std dev, [2] magnitude according to ficticios ZP
FreqStatistics = Tuple[float, float, float]


class Event(StrEnum):
	READING = "reading_event"
	ROUND = "round_event"

