from __future__ import annotations

import time
from typing import TYPE_CHECKING

import requests

from .middleware import BaseMiddleware, RetryableResponseError, RetryMiddleware

if TYPE_CHECKING:
    from .config import Config


class FetchError(Exception):
    """Levee quand fetch() epuise tous ses retries sans reponse exploitable."""


class Fetcher:
    """Telecharge le HTML brut en faisant passer chaque requete/reponse
    a travers la chaine de middlewares, via une requests.Session partagee."""

    def __init__(self, config: "Config", middlewares: list[BaseMiddleware] | None = None):
        self.config = config
        self.middlewares = middlewares or []
        self.session = requests.Session()

    def fetch(self, url: str) -> str:
        headers = {"User-Agent": self.config.fetcher.user_agent}
        max_retries = self.config.fetcher.retries
        timeout = self.config.fetcher.timeout
        base_delay = self._base_delay()

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            req_url, req_headers = url, dict(headers)
            for middleware in self.middlewares:
                req_url, req_headers = middleware.process_request(req_url, req_headers)

            wait = base_delay * (2 ** attempt)
            try:
                response = self.session.get(req_url, headers=req_headers, timeout=timeout)
                for middleware in self.middlewares:
                    response = middleware.process_response(response)
                response.raise_for_status()
                return response.text
            except RetryableResponseError as exc:
                last_exc = exc
                detail = f"HTTP {exc.response.status_code}"
                # Le serveur donne le delai a respecter (ex: 429 + Retry-After) : on le
                # respecte au lieu d'inventer notre propre backoff.
                if exc.retry_after is not None:
                    wait = exc.retry_after
            except requests.HTTPError as exc:
                # Statut HTTP definitif (ex: 404, 403), pas dans RETRYABLE_STATUS_CODES :
                # inutile de gaspiller des tentatives dessus.
                raise FetchError(f"Statut HTTP non recuperable pour {url}: {exc}") from exc
            except requests.RequestException as exc:
                last_exc = exc
                detail = type(exc).__name__

            if attempt < max_retries:
                print(f"[RETRY {url} - {detail} - prochaine tentative dans {wait:.2f}s]")
                time.sleep(wait)

        raise FetchError(
            f"Echec du fetch pour {url} apres {max_retries + 1} tentative(s)"
        ) from last_exc

    def fetch_all(self, urls: list[str]) -> list[str]:
        delay = self.config.fetcher.delay
        results = []
        for index, url in enumerate(urls):
            results.append(self.fetch(url))
            if index < len(urls) - 1:
                time.sleep(delay)
        return results

    def _base_delay(self) -> float:
        for middleware in self.middlewares:
            if isinstance(middleware, RetryMiddleware):
                return middleware.base_delay
        return 1.0
