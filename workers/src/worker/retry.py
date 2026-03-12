import random


def next_delay_seconds(attempt: int, base: float = 0.1, max_delay: float = 300.0) -> float:
    delay = min(base * (2**attempt), max_delay)
    jitter = delay * 0.1 * random.random()
    return round(delay + jitter, 3)
