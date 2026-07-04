import time
from functools import wraps
from .logger import setup_logger

logger = setup_logger(__name__)


def log_time(func):
    """A decorator that logs the execution time of a function in hours, mins, and secs."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()

        result = func(*args, **kwargs)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        hours, remainder = divmod(execution_time, 3600)
        minutes, seconds = divmod(remainder, 60)

        time_parts = []
        if hours > 0:
            time_parts.append(f"{int(hours)}h")
        if minutes > 0 or hours > 0:
            time_parts.append(f"{int(minutes)}m")
        time_parts.append(f"{seconds:.4f}s")

        time_str = " ".join(time_parts)

        logger.debug(f"Execution time of {func.__name__}: {time_str}")
        return result

    return wrapper
