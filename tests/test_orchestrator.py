from types import SimpleNamespace
from unittest.mock import patch

import requests

from dataharvest.orchestrator import Orchestrator

PAGE_1_HTML = """
<html><body>
<article>
  <h2 class="post-title"><a href="/article-1">Titre un</a></h2>
</article>
<article>
  <h2 class="post-title"><a href="/article-2">Titre deux</a></h2>
</article>
<article>
  <h2 class="post-title"><a href="">Titre sans url (rejete)</a></h2>
</article>
</body></html>
"""

PAGE_2_HTML = """
<html><body>
<article>
  <h2 class="post-title"><a href="/article-3">Titre trois</a></h2>
</article>
</body></html>
"""


def make_config(tmp_path):
    return SimpleNamespace(
        url="https://example.test/",
        pagination=SimpleNamespace(pattern="/page/{n}/", start=1, max_pages=2),
        selectors={"titre": "h2.post-title a", "url": "h2.post-title a"},
        fetcher=SimpleNamespace(delay=0.0, retries=1, timeout=5, user_agent="DataHarvest/1.0 (test)"),
        store=SimpleNamespace(backend="json", path=str(tmp_path / "articles.json")),
    )


def make_response(html, url):
    response = requests.Response()
    response.status_code = 200
    response._content = html.encode("utf-8")
    response.url = url
    return response


def test_orchestrator_run_returns_dict_with_all_expected_keys(tmp_path):
    config = make_config(tmp_path)
    orchestrator = Orchestrator(config)

    responses = {
        "https://example.test/": make_response(PAGE_1_HTML, "https://example.test/"),
        "https://example.test/page/2/": make_response(PAGE_2_HTML, "https://example.test/page/2/"),
    }

    with patch.object(orchestrator.fetcher.session, "get", side_effect=lambda url, **kw: responses[url]):
        report = orchestrator.run()

    assert set(report.keys()) == {
        "pages_scrapees",
        "items_trouves",
        "items_valides",
        "items_rejetes",
        "items_stockes",
        "duree_secondes",
    }
    assert report["pages_scrapees"] == 2
    assert report["items_trouves"] == 4  # 3 sur la page 1 + 1 sur la page 2
    assert report["items_rejetes"] == 1  # le lien avec href="" (url invalide)
    assert report["items_valides"] == 3
    assert report["items_stockes"] == 3
    assert isinstance(report["duree_secondes"], float)
    assert report["duree_secondes"] >= 0


def test_orchestrator_stores_items_progressively_across_pages(tmp_path):
    config = make_config(tmp_path)
    orchestrator = Orchestrator(config)

    responses = {
        "https://example.test/": make_response(PAGE_1_HTML, "https://example.test/"),
        "https://example.test/page/2/": make_response(PAGE_2_HTML, "https://example.test/page/2/"),
    }

    with patch.object(orchestrator.fetcher.session, "get", side_effect=lambda url, **kw: responses[url]):
        orchestrator.run()

    assert orchestrator.store.count() == 3
