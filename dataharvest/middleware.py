from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from .config import Config


class BaseMiddleware(ABC):
    @abstractmethod
    def process_request(self, url: str, headers: dict) -> tuple[str, dict]:
        """Retourne (url, headers) potentiellement modifies."""

    @abstractmethod
    def process_response(self, response: requests.Response) -> object:
        """Retourne la response potentiellement transformee."""


class RetryableResponseError(Exception):
    """Levee par RetryMiddleware quand le status de la reponse doit declencher un retry (429/5xx).

    retry_after, si present, vient de l'en-tete HTTP Retry-After et doit primer
    sur le backoff calcule par le Fetcher (le serveur donne le delai a respecter)."""

    def __init__(self, response: requests.Response, retry_after: float | None = None):
        self.response = response
        self.retry_after = retry_after
        super().__init__(f"Status {response.status_code} sur {response.url}")


class LoggingMiddleware(BaseMiddleware):
    """Logge chaque requete/reponse et son temps d'execution."""

    def __init__(self) -> None:
        self._start: float | None = None

    def process_request(self, url: str, headers: dict) -> tuple[str, dict]:
        self._start = time.perf_counter()
        print(f"[GET {url}]")
        return url, headers

    def process_response(self, response: requests.Response) -> object:
        elapsed = time.perf_counter() - self._start if self._start is not None else 0.0
        print(f"[{response.status_code} {response.reason} - {elapsed:.2f}s]")
        return response


class RetryMiddleware(BaseMiddleware):
    """Signale les reponses 429/5xx comme retryables ; le backoff est calcule ici,
    la boucle de tentatives (comptage, sleep, abandon) reste la responsabilite du Fetcher."""

    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(self, config: "Config", base_delay: float = 1.0):
        self.max_retries: int = config.fetcher.retries
        self.base_delay: float = base_delay

    def process_request(self, url: str, headers: dict) -> tuple[str, dict]:
        return url, headers

    def process_response(self, response: requests.Response) -> object:
        if response.status_code in self.RETRYABLE_STATUS_CODES:
            raise RetryableResponseError(response, retry_after=self._parse_retry_after(response))
        return response

    def backoff_delay(self, attempt: int) -> float:
        return self.base_delay * (2 ** attempt)

    @staticmethod
    def _parse_retry_after(response: requests.Response) -> float | None:
        """Parse l'en-tete Retry-After (RFC 9110) : soit un nombre de secondes,
        soit une date HTTP. Retourne None si absent ou invalide."""
        value = response.headers.get("Retry-After")
        if value is None:
            return None

        value = value.strip()
        try:
            return max(float(value), 0.0)
        except ValueError:
            pass

        try:
            target = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if target is None:
            return None
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        return max((target - datetime.now(timezone.utc)).total_seconds(), 0.0)
