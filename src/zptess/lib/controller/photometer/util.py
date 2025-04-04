import statistics


from typing import  Sequence, Tuple

from ... import CentralTendency

def mode(sequence: Sequence) -> float:
    try:
        result = statistics.multimode(sequence)
        if len(result) != 1:     # To make it compatible with my previous software
            raise statistics.StatisticsError
        result = result[0]
    except AttributeError: # Previous to Python 3.8
        result = statistics.mode(sequence)
    return result

def best(sequence: Sequence) -> Tuple[CentralTendency, float]:
    try:
        result = mode(sequence)
        central = CentralTendency.MODE
    except statistics.StatisticsError:
        result = statistics.median_low(sequence)
        central = CentralTendency.MEDIAN
    return central, result