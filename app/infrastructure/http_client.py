"""Cliente HTTP con retry, backoff y rotación de User-Agent."""
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.infrastructure.rate_limiter import next_user_agent, retry_with_backoff, with_delay


def create_session(
    base_headers: Optional[dict] = None,
    retries: int = 3,
    backoff_factor: float = 0.5,
) -> requests.Session:
    """Crea una sesión requests con reintentos y adaptador configurado."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
    session.mount("http://", HTTPAdapter(max_retries=retry_strategy))
    session.headers.update(base_headers or {})
    return session


def get_with_retry(
    url: str,
    session: Optional[requests.Session] = None,
    params: Optional[dict] = None,
    referer: Optional[str] = None,
    delay_before: bool = True,
) -> requests.Response:
    """
    GET con User-Agent rotado, opcional delay y retry con backoff.
    """
    if delay_before:
        with_delay(0.3, 0.8)
    s = session or requests.Session()
    headers = {"User-Agent": next_user_agent()}
    if referer:
        headers["Referer"] = referer

    @retry_with_backoff(max_attempts=3, min_wait=1.0, max_wait=10.0)
    def _get():
        return s.get(url, params=params, headers=headers, timeout=15)

    return _get()
