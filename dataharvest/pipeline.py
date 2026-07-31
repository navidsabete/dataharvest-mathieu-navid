from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from .config import Config


class BasePipeline(ABC):
    @abstractmethod
    def process(self, html: str) -> list[dict]:
        """Retourne TOUJOURS une liste, jamais None."""

    @abstractmethod
    def next_page_url(self, html: str, current_url: str) -> str | None:
        """Retourne l'URL de la page suivante ou None si fin."""


class GenericPipeline(BasePipeline):
    """Extrait des items depuis du HTML brut a partir des selecteurs CSS de la config.

    Deux modes :
    - Sans item_selector (par defaut) : chaque champ a son propre selecteur CSS
      applique a toute la page ; les items sont reconstruits en associant les
      correspondances par position (le n-ieme element trouve pour 'titre'
      correspond au n-ieme trouve pour 'url', etc.). Simple, mais suppose que
      chaque champ apparait exactement une fois par item -- un champ absent
      pour certains items seulement (ex: le domaine source d'un post "Ask HN"
      sur news.ycombinator.com, absent des posts sans lien externe) desaligne
      tout le reste.
    - Avec item_selector : chaque champ est cherche a l'interieur de son propre
      conteneur d'item (avec repli sur l'element suivant immediat, utile pour
      les sites qui etalent un item sur deux lignes de table). Un champ absent
      pour un item donne juste une chaine vide pour CET item, sans decaler
      les autres."""

    def __init__(self, selectors: dict, base_url: str = "", item_selector: str | None = None):
        self.selectors = selectors
        self.base_url = base_url
        self.item_selector = item_selector

    def process(self, html: str) -> list[dict]:
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        if self.item_selector:
            return self._process_scoped(soup)
        return self._process_flat(soup)

    def _process_flat(self, soup: BeautifulSoup) -> list[dict]:
        parsed = {field: self._parse_selector(selector) for field, selector in self.selectors.items()}
        matches = {field: soup.select(css) for field, (css, _extractor) in parsed.items()}
        count = max((len(tags) for tags in matches.values()), default=0)

        items = []
        for index in range(count):
            item = {
                field: self._extract_value(
                    tags[index] if index < len(tags) else None, field, parsed[field][1]
                )
                for field, tags in matches.items()
            }
            items.append(item)
        return items

    def _process_scoped(self, soup: BeautifulSoup) -> list[dict]:
        parsed = {field: self._parse_selector(selector) for field, selector in self.selectors.items()}
        containers = soup.select(self.item_selector)
        container_ids = {id(c) for c in containers}

        items = []
        for container in containers:
            sibling = container.find_next_sibling()
            if sibling is not None and id(sibling) in container_ids:
                # Le "sibling" est en fait l'item suivant (item_selector le
                # matche aussi), pas une extension du meme item -- ne pas
                # s'y replier sous peine de voler ses champs.
                sibling = None

            item = {}
            for field, (css, extractor) in parsed.items():
                match = container.select_one(css)
                if match is None and sibling is not None:
                    match = sibling.select_one(css)
                item[field] = self._extract_value(match, field, extractor)
            items.append(item)
        return items

    def next_page_url(self, html: str, current_url: str) -> str | None:
        return None

    @staticmethod
    def _parse_selector(selector: str) -> tuple[str, str | None]:
        """Scinde un selecteur de la forme 'css::attr(nom)' ou 'css::text' (syntaxe
        inspiree de Scrapy). Retourne (css, extracteur), extracteur valant un nom
        d'attribut, 'text', ou None (comportement par defaut, voir _extract_value)."""
        if selector.endswith(")") and "::attr(" in selector:
            css, _, tail = selector.partition("::attr(")
            return css.strip(), tail[:-1].strip()
        if selector.endswith("::text"):
            return selector[: -len("::text")].strip(), "text"
        return selector, None

    def _extract_value(self, tag, field: str, extractor: str | None) -> str:
        if tag is None:
            return ""

        if extractor and extractor != "text":
            value = tag.get(extractor)
            if isinstance(value, list):
                value = " ".join(value)
            value = value or ""
            return self._absolutize(value) if extractor == "href" and value else value

        if extractor != "text" and field == "url":
            href = tag.get("href") or ""
            if href:
                return self._absolutize(href)

        text = tag.get_text(" ", strip=True)
        if text:
            return text

        for attr in ("datetime", "content", "title", "href"):
            value = tag.get(attr)
            if value:
                return self._absolutize(value) if attr == "href" else value
        return ""

    def _absolutize(self, href: str) -> str:
        if href.startswith(("http://", "https://")):
            return href
        return urljoin(self.base_url, href) if self.base_url else href


class PaginationPipeline(GenericPipeline):
    """Etend GenericPipeline avec la logique de pagination : construit l'URL de la
    page suivante selon pagination_config.pattern, s'arrete a max_pages ou des qu'une
    page ne contient plus d'items."""

    def __init__(
        self,
        selectors: dict,
        pagination_config,
        base_url: str = "",
        item_selector: str | None = None,
    ):
        super().__init__(selectors, base_url=base_url, item_selector=item_selector)
        self.pagination_config = pagination_config
        self._page_number = pagination_config.start

    def next_page_url(self, html: str, current_url: str) -> str | None:
        if not self.process(html):
            return None

        pattern = getattr(self.pagination_config, "pattern", None)
        if not pattern:
            return None

        self._page_number += 1
        if self._page_number > self.pagination_config.max_pages:
            return None

        next_path = pattern.format(n=self._page_number)
        return urljoin(current_url, next_path)
