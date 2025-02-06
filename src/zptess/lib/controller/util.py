import statistics


from typing import  Sequence


def mode(sequence: Sequence):
    try:
        result = statistics.multimode(sequence)
        if len(result) != 1:     # To make it compatible with my previous software
            raise statistics.StatisticsError
        result = result[0]
    except AttributeError: # Previous to Python 3.8
        result = statistics.mode(sequence)
    return result
