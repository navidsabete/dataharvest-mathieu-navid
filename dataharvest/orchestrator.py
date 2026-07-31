from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .fetcher import Fetcher
from .middleware import LoggingMiddleware, RetryMiddleware
from .pipeline import PaginationPipeline
from .validator import Validator
from .store import Store

if TYPE_CHECKING:
    from .config import Config


class Orchestrator:
    """Assemble tous les composants et pilote un scraping complet.
    Seul composant qui connait Fetcher, Pipeline, Validator et Store a la fois."""

    def __init__(self, config: "Config"):
        self.config = config
        self.fetcher = Fetcher(config, middlewares=[LoggingMiddleware(), RetryMiddleware(config)])
        # item_selector optionnel (cle top-level "item_selector" dans le YAML) : necessaire
        # pour les sites ou un champ est absent pour certains items seulement (ex: le domaine
        # source sur news.ycombinator.com, absent des posts "Ask HN") -- voir pipeline.py.
        item_selector = getattr(config, "item_selector", None)
        self.pipeline = PaginationPipeline(
            config.selectors, config.pagination, base_url=config.url, item_selector=item_selector
        )
        # required_fields par defaut = pseudo-code du sujet (section 4.7), mais surchargeable
        # par site via un bloc optionnel "validator: required_fields: [...]" dans le YAML --
        # necessaire des que le champ identifiant principal du site n'est pas litteralement
        # nomme 'titre'/'url' (ex: quotes.toscrape.com n'a pas d'URL par citation).
        required_fields = getattr(getattr(config, "validator", None), "required_fields", None) or ["titre", "url"]
        self.validator = Validator(required_fields=required_fields)
        self.store = Store(config.store.backend, config.store.path)

    def run(self) -> dict:
        """Lance le scraping complet : pagine automatiquement, valide et stocke
        chaque page au fur et a mesure. Retourne un rapport de session."""
        start = time.perf_counter()

        pages_scrapees = 0
        items_trouves = 0
        items_valides = 0
        items_rejetes = 0
        items_stockes = 0

        url = self.config.url
        while url:
            html = self.fetcher.fetch(url)
            items = self.pipeline.process(html)
            pages_scrapees += 1
            items_trouves += len(items)

            valides, rejetes = self.validator.validate(items)
            items_valides += len(valides)
            items_rejetes += len(rejetes)

            if valides:
                items_stockes += self.store.save(valides)

            url = self.pipeline.next_page_url(html, url)

        duree = time.perf_counter() - start
        return self._build_report(
            pages=pages_scrapees,
            found=items_trouves,
            valid=items_valides,
            rejected=items_rejetes,
            stored=items_stockes,
            duree=duree,
        )

    def _build_report(self, pages: int, found: int, valid: int, rejected: int, stored: int, duree: float) -> dict:
        return {
            "pages_scrapees": pages,
            "items_trouves": found,
            "items_valides": valid,
            "items_rejetes": rejected,
            "items_stockes": stored,
            "duree_secondes": duree,
        }
