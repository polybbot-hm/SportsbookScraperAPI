"""Rate limiting y rotación de User-Agent para scraping."""
import time
from typing import Callable, Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


def get_user_agent_rotator():
    """Genera User-Agent rotando entre varios. Sin dependencia de fake-useragent por simplicidad inicial."""
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    idx = [0]

    def next_ua() -> str:
        ua = agents[idx[0] % len(agents)]
        idx[0] += 1
        return ua

    return next_ua


_next_ua = get_user_agent_rotator()


def next_user_agent() -> str:
    """Devuelve el siguiente User-Agent de la rotación."""
    return _next_ua()


def with_delay(min_seconds: float = 0.5, max_seconds: float = 2.0) -> None:
    """Pequeña pausa entre requests para no saturar el servidor."""
    time.sleep(min_seconds)


def retry_with_backoff(
    fn: Optional[Callable] = None,
    *,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
):
    """Decorador que reintenta con backoff exponencial en excepciones de red."""
    def decorator(func):
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
            reraise=True,
        )(func)

    if fn is not None:
        return decorator(fn)
    return decorator
