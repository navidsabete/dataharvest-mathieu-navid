from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

from dataharvest.fetcher import Fetcher, FetchError
from dataharvest.middleware import LoggingMiddleware, RetryMiddleware


def make_config(**fetcher_overrides):
    defaults = {
        "delay": 0.0,
        "retries": 2,
        "timeout": 5,
        "user_agent": "DataHarvest/1.0 (+contact@ipssi.fr)",
    }
    defaults.update(fetcher_overrides)
    return SimpleNamespace(fetcher=SimpleNamespace(**defaults))


def make_response(status_code, text="<html>ok</html>", headers=None):
    response = requests.Response()
    response.status_code = status_code
    response.reason = "REASON"
    response.url = "https://example.test/"
    response._content = text.encode("utf-8")
    if headers:
        response.headers.update(headers)
    return response


def make_fetcher(config, base_delay=0.01):
    return Fetcher(config, middlewares=[LoggingMiddleware(), RetryMiddleware(config, base_delay=base_delay)])


def test_fetch_returns_non_empty_string_on_success():
    config = make_config()
    fetcher = make_fetcher(config)

    with patch.object(fetcher.session, "get", return_value=make_response(200, "<html>contenu</html>")):
        html = fetcher.fetch("https://example.test/")

    assert isinstance(html, str)
    assert html != ""
    assert "contenu" in html


def test_fetch_raises_fetch_error_after_retries_exhausted():
    config = make_config(retries=2)
    fetcher = make_fetcher(config)

    with patch.object(fetcher.session, "get", side_effect=requests.ConnectionError("boom")):
        with pytest.raises(FetchError):
            fetcher.fetch("https://example.test/")


def test_fetch_raises_fetch_error_immediately_on_non_retryable_status():
    config = make_config(retries=3)
    fetcher = make_fetcher(config)
    call_count = {"n": 0}

    def fake_get(*args, **kwargs):
        call_count["n"] += 1
        return make_response(404)

    with patch.object(fetcher.session, "get", side_effect=fake_get):
        with pytest.raises(FetchError):
            fetcher.fetch("https://example.test/")

    assert call_count["n"] == 1  # pas de retry gaspille sur un 404


def test_fetch_respects_retry_after_header_over_computed_backoff():
    config = make_config(retries=1)
    fetcher = make_fetcher(config, base_delay=5.0)
    responses = [make_response(429, headers={"Retry-After": "0.01"}), make_response(200, "ok")]

    with patch.object(fetcher.session, "get", side_effect=responses):
        with patch("dataharvest.fetcher.time.sleep") as mocked_sleep:
            fetcher.fetch("https://example.test/")

    mocked_sleep.assert_called_once_with(0.01)


def test_fetch_uses_user_agent_from_config():
    config = make_config(user_agent="MonBot/2.0 (+contact@example.com)")
    fetcher = make_fetcher(config)
    captured_headers = {}

    def fake_get(url, headers=None, timeout=None):
        captured_headers.update(headers)
        return make_response(200)

    with patch.object(fetcher.session, "get", side_effect=fake_get):
        fetcher.fetch("https://example.test/")

    assert captured_headers["User-Agent"] == "MonBot/2.0 (+contact@example.com)"


def test_fetch_all_respects_delay_between_urls():
    config = make_config(delay=0.02)
    fetcher = make_fetcher(config)

    with patch.object(fetcher.session, "get", return_value=make_response(200)):
        with patch("dataharvest.fetcher.time.sleep") as mocked_sleep:
            fetcher.fetch_all(["https://example.test/a", "https://example.test/b", "https://example.test/c"])

    # 2 pauses entre 3 URLs, jamais apres la derniere
    assert mocked_sleep.call_count == 2
    mocked_sleep.assert_called_with(0.02)
