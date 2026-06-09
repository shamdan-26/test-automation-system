from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

from utils.logger import get_logger

F = TypeVar("F", bound=Callable[..., Any])
log = get_logger(__name__)


def retry(
    attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator: retry a function on failure with exponential backoff."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == attempts:
                        log.error(
                            "All retry attempts exhausted",
                            func=func.__name__,
                            attempts=attempts,
                            error=str(exc),
                        )
                        raise
                    log.warning(
                        "Attempt failed, retrying",
                        func=func.__name__,
                        attempt=attempt,
                        delay=current_delay,
                        error=str(exc),
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

        return wrapper  # type: ignore[return-value]

    return decorator
