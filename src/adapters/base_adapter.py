"""
Base adapter interface for all data sources.

Defines the contract that all adapters (OpenParliament, LEGISinfo, etc.)
must implement. Ensures consistent error handling, rate limiting, and
response format across all data sources.

Responsibility: Abstract base class defining adapter contract
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Generic,
    TypeVar,
    Any,
    Optional,
    Callable,
    Awaitable,
    List,
    Tuple,
    Dict,
)
import asyncio
import logging
import random
import time
import math

import httpx

from ..models.adapter_models import (
    AdapterResponse,
    AdapterStatus,
    AdapterError,
    AdapterMetrics,
)
from ..utils.rate_limiter import RateLimiter
from ..utils.http_cache import CacheValidator


# Generic type for normalized data models
T = TypeVar('T')


class CircuitBreakerOpenError(RuntimeError):
    """Raised when the circuit breaker is open for the adapter."""


@dataclass
class _HttpMetricsState:
    """Internal accumulator for HTTP-related telemetry."""

    request_count: int = 0
    not_modified: int = 0
    retry_429: int = 0
    retry_5xx: int = 0
    retry_other: int = 0
    latencies_ms: List[float] = field(default_factory=list)

    def reset(self) -> None:
        self.request_count = 0
        self.not_modified = 0
        self.retry_429 = 0
        self.retry_5xx = 0
        self.retry_other = 0
        self.latencies_ms.clear()

    def record_latency(self, elapsed_seconds: float) -> None:
        self.latencies_ms.append(max(elapsed_seconds, 0.0) * 1000.0)


class BaseAdapter(ABC, Generic[T]):
    """Shared adapter infrastructure for external data sources."""

    def __init__(
        self,
        source_name: str,
        rate_limit_per_second: float = 0.5,
        max_retries: int = 3,
        timeout_seconds: int = 30,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_cooldown: float = 120.0,
        telemetry_handler: Optional[Callable[[AdapterMetrics], None]] = None,
    ) -> None:
        self.source_name = source_name
        self.rate_limit_per_second = rate_limit_per_second
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.circuit_breaker_threshold = max(1, circuit_breaker_threshold)
        self.circuit_breaker_cooldown = max(5.0, circuit_breaker_cooldown)

        self.rate_limiter = RateLimiter(rate=rate_limit_per_second, burst=1)
        self.logger = logging.getLogger(f"adapter.{source_name}")
        self._current_retry_attempts = 0
        self._consecutive_failures = 0
        self._circuit_open_until: Optional[float] = None
        self._http_metrics = _HttpMetricsState()
        self._cache_validators: Dict[str, CacheValidator] = {}
        self._telemetry_handler = telemetry_handler

    @abstractmethod
    async def fetch(self, **kwargs: Any) -> AdapterResponse[T]:
        """Retrieve data from the upstream source."""

    @abstractmethod
    def normalize(self, raw_data: Any) -> T:
        """Convert raw source payload into a domain model instance."""

    def _build_success_response(
        self,
        data: list[T],
        errors: list[AdapterError],
        start_time: datetime,
        cache_ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AdapterResponse[T]:
        """
        Build a successful AdapterResponse.
        
        Helper method to construct response with calculated metrics.
        """
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # Determine status
        if not errors:
            status = AdapterStatus.SUCCESS
        else:
            status = AdapterStatus.PARTIAL_SUCCESS
        
        # Calculate cache expiry
        cache_until = None
        if cache_ttl_seconds:
            from datetime import timedelta
            cache_until = end_time + timedelta(seconds=cache_ttl_seconds)
        
        avg_latency, p95_latency = self._latency_stats()

        response = AdapterResponse(
            status=status,
            data=data,
            errors=errors,
            metrics=AdapterMetrics(
                records_attempted=len(data) + len(errors),
                records_succeeded=len(data),
                records_failed=len(errors),
                duration_seconds=duration,
                rate_limit_hits=self.rate_limiter.pop_hit_count(),
                retry_count=self._current_retry_attempts,
                http_request_count=self._http_metrics.request_count,
                http_not_modified=self._http_metrics.not_modified,
                http_retry_429=self._http_metrics.retry_429,
                http_retry_5xx=self._http_metrics.retry_5xx,
                http_retry_other=self._http_metrics.retry_other,
                http_latency_avg_ms=avg_latency,
                http_latency_p95_ms=p95_latency,
            ),
            source=self.source_name,
            fetch_timestamp=end_time,
            cache_until=cache_until,
            metadata=metadata or {},
        )
        self._emit_metrics_log(response.metrics)
        return response

    def _build_failure_response(
        self,
        error: Exception,
        start_time: datetime,
        retryable: bool = False,
    ) -> AdapterResponse[T]:
        """
        Build a failed AdapterResponse.
        
        Used when entire fetch operation fails (source unavailable, etc.)
        """
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        avg_latency, p95_latency = self._latency_stats()

        response = AdapterResponse(
            status=AdapterStatus.SOURCE_UNAVAILABLE if retryable else AdapterStatus.FAILURE,
            data=None,
            errors=[AdapterError(
                timestamp=end_time,
                error_type=type(error).__name__,
                message=str(error),
                context={"adapter": self.source_name},
                retryable=retryable
            )],
            metrics=AdapterMetrics(
                records_attempted=0,
                records_succeeded=0,
                records_failed=0,
                duration_seconds=duration,
                rate_limit_hits=self.rate_limiter.pop_hit_count(),
                retry_count=self._current_retry_attempts,
                http_request_count=self._http_metrics.request_count,
                http_not_modified=self._http_metrics.not_modified,
                http_retry_429=self._http_metrics.retry_429,
                http_retry_5xx=self._http_metrics.retry_5xx,
                http_retry_other=self._http_metrics.retry_other,
                http_latency_avg_ms=avg_latency,
                http_latency_p95_ms=p95_latency,
            ),
            source=self.source_name,
            fetch_timestamp=end_time,
            metadata={},
        )
        self._emit_metrics_log(response.metrics, failure=True)
        return response

    def _reset_metrics(self) -> None:
        """Reset internal counters for rate limit hits and retry attempts."""
        self._current_retry_attempts = 0
        self.rate_limiter.pop_hit_count()
        self._http_metrics.reset()

    def _cache_key(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not params:
            return url
        parts: List[str] = []
        for key in sorted(params):
            value = params[key]
            if isinstance(value, (list, tuple)):
                for item in value:
                    parts.append(f"{key}={item}")
            else:
                parts.append(f"{key}={value}")
        query = "&".join(parts)
        return f"{url}?{query}"

    def _cache_validator(self, cache_key: str) -> CacheValidator:
        validator = self._cache_validators.get(cache_key)
        if validator is None:
            validator = CacheValidator()
            self._cache_validators[cache_key] = validator
        return validator

    async def _http_get(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        cache_key: Optional[str] = None,
        use_rate_limiter: bool = True,
    ) -> httpx.Response:
        if use_rate_limiter:
            await self.rate_limiter.acquire()

        key = cache_key or self._cache_key(url, params)
        validator = self._cache_validator(key)
        request_headers = validator.apply(headers or {})

        request_kwargs: Dict[str, Any] = {}
        if params is not None:
            request_kwargs["params"] = params
        if request_headers:
            request_kwargs["headers"] = request_headers

        response = await self._request_with_retries(
            client.get,
            url,
            **request_kwargs,
        )

        if response.status_code != httpx.codes.NOT_MODIFIED:
            validator.update_from_response(response)

        return response

    async def _request_with_retries(
        self,
        request_callable: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute an HTTP request with retry logic and metrics tracking.
        """
        attempt = 0
        while True:
            self._ensure_circuit_allowance()
            attempt += 1
            start_ns = time.perf_counter()
            response: Optional[httpx.Response] = None
            try:
                response = await request_callable(*args, **kwargs)
                elapsed = time.perf_counter() - start_ns
                self._record_http_attempt(elapsed, response.status_code)

                if self._should_retry_status(response.status_code):
                    if attempt > self.max_retries:
                        self._register_failure()
                        response.raise_for_status()
                    delay = self._status_retry_delay(response, attempt)
                    self._register_status_retry(response.status_code, delay, attempt)
                    await asyncio.sleep(delay)
                    continue

                self._consecutive_failures = 0
                self._circuit_open_until = None
                return response

            except httpx.HTTPError as exc:
                elapsed = time.perf_counter() - start_ns
                self._record_http_attempt(elapsed, status_code=None)

                if attempt > self.max_retries or not self._is_retryable_exception(exc):
                    self._register_failure()
                    raise

                delay = self._exception_retry_delay(exc, attempt)
                self._register_exception_retry(exc, delay, attempt)
                await asyncio.sleep(delay)

            except Exception:
                elapsed = time.perf_counter() - start_ns
                self._record_http_attempt(elapsed, status_code=None)
                self._register_failure()
                raise

    def _ensure_circuit_allowance(self) -> None:
        if self._circuit_open_until is None:
            return
        now = time.monotonic()
        if now >= self._circuit_open_until:
            self.logger.info(
                "%s circuit breaker reset after cooldown", self.source_name
            )
            self._circuit_open_until = None
            self._consecutive_failures = 0
            return
        raise CircuitBreakerOpenError(
            f"Circuit breaker open for {self.source_name}; retry after "
            f"{self._circuit_open_until - now:.1f}s"
        )

    def _record_http_attempt(self, elapsed: float, status_code: Optional[int]) -> None:
        self._http_metrics.request_count += 1
        self._http_metrics.record_latency(elapsed)
        if status_code == 304:
            self._http_metrics.not_modified += 1

    def _should_retry_status(self, status_code: int) -> bool:
        if status_code in (429, 503):
            return True
        if 500 <= status_code < 600:
            return True
        if status_code in (408, 425):
            return True
        return False

    def _status_retry_delay(
        self,
        response: httpx.Response,
        attempt: int,
    ) -> float:
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                return float(retry_after) + random.uniform(0.25, 0.75)
        base = min(0.5 * (2 ** (attempt - 1)), 30.0)
        jitter = random.uniform(0, 0.5)
        return base + jitter

    def _register_status_retry(
        self,
        status_code: int,
        delay: float,
        attempt: int,
    ) -> None:
        if status_code == 429:
            self._http_metrics.retry_429 += 1
        elif 500 <= status_code < 600:
            self._http_metrics.retry_5xx += 1
        else:
            self._http_metrics.retry_other += 1
        self._current_retry_attempts += 1
        self.logger.warning(
            "%s received status %s. Retrying in %.2fs (attempt %s/%s)",
            self.source_name,
            status_code,
            delay,
            attempt,
            self.max_retries,
        )

    def _is_retryable_exception(self, exc: httpx.HTTPError) -> bool:
        return isinstance(
            exc,
            (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
            ),
        )

    def _exception_retry_delay(self, exc: httpx.HTTPError, attempt: int) -> float:
        base = min(1.0 * (2 ** (attempt - 1)), 45.0)
        jitter = random.uniform(0.25, 0.75)
        return base + jitter

    def _register_exception_retry(
        self,
        exc: httpx.HTTPError,
        delay: float,
        attempt: int,
    ) -> None:
        self._http_metrics.retry_other += 1
        self._current_retry_attempts += 1
        self.logger.warning(
            "%s request raised %s. Retrying in %.2fs (attempt %s/%s)",
            self.source_name,
            type(exc).__name__,
            delay,
            attempt,
            self.max_retries,
        )

    def _register_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures < self.circuit_breaker_threshold:
            return
        self._circuit_open_until = time.monotonic() + self.circuit_breaker_cooldown
        self.logger.error(
            "%s circuit breaker opened for %.1fs after %s consecutive failures",
            self.source_name,
            self.circuit_breaker_cooldown,
            self.circuit_breaker_threshold,
        )
        self._consecutive_failures = 0

    def _latency_stats(self) -> Tuple[float, float]:
        if not self._http_metrics.latencies_ms:
            return 0.0, 0.0
        values = sorted(self._http_metrics.latencies_ms)
        average = sum(values) / len(values)
        index = max(0, min(len(values) - 1, math.ceil(len(values) * 0.95) - 1))
        return average, values[index]

    def _emit_metrics_log(
        self,
        metrics: AdapterMetrics,
        *,
        failure: bool = False,
    ) -> None:
        payload = metrics.model_dump()
        payload["adapter"] = self.source_name
        payload["outcome"] = "failure" if failure else "success"
        self.logger.info("adapter.metrics", extra={"adapter_metrics": payload})
        if self._telemetry_handler:
            try:
                self._telemetry_handler(metrics)
            except Exception as exc:
                self.logger.warning(
                    "%s telemetry handler failed: %s",
                    self.source_name,
                    exc,
                    exc_info=True,
                )
