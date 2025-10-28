from __future__ import annotations

import random
import time
from typing import Iterable, Mapping, Sequence

import requests


DEFAULT_RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class HttpRequestError(RuntimeError):
    """Raised when a retried HTTP request ultimately fails."""

    def __init__(self, url: str, status: int | None, message: str | None = None) -> None:
        detail = message or "HTTP request failed"
        super().__init__(f"{detail} (url={url!r}, status={status})")
        self.url = url
        self.status = status


def fetch_with_backoff(
    url: str,
    *,
    method: str = "get",
    params: Mapping[str, object] | None = None,
    headers: Mapping[str, str] | None = None,
    data: Mapping[str, object] | None = None,
    timeout: float = 30.0,
    retries: int = 4,
    backoff_factor: float = 1.7,
    jitter: float = 0.3,
    retry_status: Iterable[int] | None = None,
    session: requests.Session | None = None,
    allowed_status: Sequence[int] | None = None,
) -> requests.Response:
    """Perform an HTTP request with exponential backoff and jitter."""

    request_fn = getattr(session or requests, method.lower(), None)
    if request_fn is None:
        raise ValueError(f"Unsupported HTTP method: {method}")

    attempt = 0
    last_error: Exception | None = None
    retry_status_set = set(retry_status or DEFAULT_RETRY_STATUS)
    allowed_status = tuple(allowed_status or ())

    while attempt <= retries:
        try:
            response = request_fn(
                url,
                params=params,
                headers=headers,
                data=data,
                timeout=timeout,
            )
            if allowed_status:
                if response.status_code in allowed_status:
                    return response
                raise HttpRequestError(url, response.status_code)
            if response.status_code in retry_status_set:
                raise HttpRequestError(url, response.status_code)
            response.raise_for_status()
            return response
        except Exception as exc:  # pragma: no cover - network failure path varies
            last_error = exc
            attempt += 1
            if attempt > retries:
                break
            delay = (backoff_factor ** attempt)
            if jitter:
                delay += random.uniform(0, jitter)
            time.sleep(delay)

    if isinstance(last_error, HttpRequestError):
        raise last_error
    raise HttpRequestError(url, None, message=str(last_error) if last_error else None)
