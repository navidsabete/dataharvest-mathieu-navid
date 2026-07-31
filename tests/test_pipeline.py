from types import SimpleNamespace

from dataharvest.pipeline import GenericPipeline, PaginationPipeline

SELECTORS = {
    "titre": "h2.post-title a",
    "url": "h2.post-title a",
    "date": "time",
    "categorie": ".cat-links a",
}

HTML_WITH_ITEMS = """
<html><body>
<article>
  <h2 class="post-title"><a href="/article-1">Titre un</a></h2>
  <time datetime="2026-07-01">1 juillet 2026</time>
  <span class="cat-links"><a href="/cat/tech">Tech</a></span>
</article>
<article>
  <h2 class="post-title"><a href="https://example.com/article-2">Titre deux</a></h2>
  <time datetime="2026-07-02"></time>
  <span class="cat-links"><a href="/cat/ia">IA</a></span>
</article>
</body></html>
"""


def test_process_returns_list_even_on_empty_html():
    pipeline = GenericPipeline(SELECTORS)
    assert pipeline.process("") == []
    assert isinstance(pipeline.process("<html></html>"), list)


def test_process_does_not_raise_on_missing_selector():
    selectors = dict(SELECTORS, auteur=".does-not-exist")
    pipeline = GenericPipeline(selectors, base_url="https://example.test")
    items = pipeline.process(HTML_WITH_ITEMS)
    assert len(items) == 2
    assert all(item["auteur"] == "" for item in items)


def test_process_extracts_fields_and_resolves_relative_urls():
    pipeline = GenericPipeline(SELECTORS, base_url="https://www.blogdumoderateur.com")
    items = pipeline.process(HTML_WITH_ITEMS)

    assert items[0]["titre"] == "Titre un"
    assert items[0]["url"] == "https://www.blogdumoderateur.com/article-1"
    assert items[0]["categorie"] == "Tech"

    # URL deja absolue : laissee telle quelle
    assert items[1]["url"] == "https://example.com/article-2"
    # pas de texte dans <time>, mais un attribut datetime : utilise en fallback
    assert items[1]["date"] == "2026-07-02"


def test_generic_pipeline_next_page_url_is_always_none():
    pipeline = GenericPipeline(SELECTORS)
    assert pipeline.next_page_url(HTML_WITH_ITEMS, "https://example.test/") is None


def test_pagination_pipeline_advances_page_number():
    pagination_config = SimpleNamespace(pattern="/page/{n}/", start=1, max_pages=3)
    pipeline = PaginationPipeline(SELECTORS, pagination_config, base_url="https://www.blogdumoderateur.com")

    url = "https://www.blogdumoderateur.com/page/1/"
    next_url = pipeline.next_page_url(HTML_WITH_ITEMS, url)
    assert next_url == "https://www.blogdumoderateur.com/page/2/"

    next_url = pipeline.next_page_url(HTML_WITH_ITEMS, next_url)
    assert next_url == "https://www.blogdumoderateur.com/page/3/"


def test_pagination_pipeline_stops_at_max_pages():
    pagination_config = SimpleNamespace(pattern="/page/{n}/", start=1, max_pages=2)
    pipeline = PaginationPipeline(SELECTORS, pagination_config, base_url="https://www.blogdumoderateur.com")

    url = "https://www.blogdumoderateur.com/page/1/"
    next_url = pipeline.next_page_url(HTML_WITH_ITEMS, url)
    assert next_url == "https://www.blogdumoderateur.com/page/2/"

    next_url = pipeline.next_page_url(HTML_WITH_ITEMS, next_url)
    assert next_url is None


def test_pagination_pipeline_stops_when_page_has_no_items():
    pagination_config = SimpleNamespace(pattern="/page/{n}/", start=1, max_pages=10)
    pipeline = PaginationPipeline(SELECTORS, pagination_config)

    assert pipeline.next_page_url("<html></html>", "https://example.test/page/1/") is None


HTML_WITH_MISSING_FIELD = """
<html><body>
<article>
  <h2 class="post-title"><a href="/article-1">Titre un</a></h2>
  <time datetime="2026-07-01">1 juillet 2026</time>
  <span class="cat-links"><a href="/cat/tech">Tech</a></span>
</article>
<article>
  <h2 class="post-title"><a href="/article-2">Titre deux (sans categorie)</a></h2>
  <time datetime="2026-07-02">2 juillet 2026</time>
</article>
<article>
  <h2 class="post-title"><a href="/article-3">Titre trois</a></h2>
  <time datetime="2026-07-03">3 juillet 2026</time>
  <span class="cat-links"><a href="/cat/ia">IA</a></span>
</article>
</body></html>
"""


def test_item_selector_scopes_fields_to_their_own_container():
    # Sans item_selector (mode flat), l'absence de categorie sur l'item 2
    # decalerait la categorie "IA" de l'item 3 vers l'item 2. Avec
    # item_selector, chaque champ reste scope a son propre <article>.
    pipeline = GenericPipeline(SELECTORS, base_url="https://example.test", item_selector="article")
    items = pipeline.process(HTML_WITH_MISSING_FIELD)

    assert len(items) == 3
    assert items[0]["categorie"] == "Tech"
    assert items[1]["categorie"] == ""
    assert items[2]["categorie"] == "IA"
    assert items[2]["titre"] == "Titre trois"


def test_item_selector_falls_back_to_next_sibling_element():
    # Utile pour les sites qui etalent un item sur deux elements adjacents
    # (ex: news.ycombinator.com : ligne titre + ligne score/commentaires).
    html = """
    <html><body>
    <div class="row-a"><span class="titre">Un</span></div>
    <div class="row-b"><span class="score">10</span></div>
    </body></html>
    """
    selectors = {"titre": ".titre", "score": ".score"}
    pipeline = GenericPipeline(selectors, item_selector=".row-a")
    items = pipeline.process(html)

    assert items == [{"titre": "Un", "score": "10"}]
