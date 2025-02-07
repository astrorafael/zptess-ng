import statistics


from typing import  Sequence


def mode(sequence: Sequence) -> float:
    try:
        result = statistics.multimode(sequence)
        if len(result) != 1:     # To make it compatible with my previous software
            raise statistics.StatisticsError
        result = result[0]
    except AttributeError: # Previous to Python 3.8
        result = statistics.mode(sequence)
    return result

def best(sequence: Sequence) -> float:
	try:
		result = mode(sequence)
	except statistics.StatisticsError:
		result = statistics.median_low(sequence)
	return result