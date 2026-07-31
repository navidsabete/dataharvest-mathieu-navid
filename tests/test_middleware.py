from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace

import requests

from dataharvest.middleware import LoggingMiddleware, RetryableResponseError, RetryMiddleware


def make_config(retries=3):
    return SimpleNamespace(fetcher=SimpleNamespace(retries=retries))


def make_response(status_code, headers=None):
    response = requests.Response()
    response.status_code = status_code
    response.reason = "REASON"
    response.url = "https://example.test/"
    response.headers.update(headers or {})
    return response


def test_logging_middleware_process_request_and_response(capsys):
    middleware = LoggingMiddleware()
    url, headers = middleware.process_request("https://example.test/", {"User-Agent": "x"})
    middleware.process_response(make_response(200))

    captured = capsys.readouterr()
    assert url == "https://example.test/"
    assert "[GET https://example.test/]" in captured.out
    assert "[200 REASON" in captured.out


def test_retry_middleware_backoff_delay_is_exponential():
    middleware = RetryMiddleware(make_config(), base_delay=2.0)
    assert middleware.backoff_delay(0) == 2.0
    assert middleware.backoff_delay(1) == 4.0
    assert middleware.backoff_delay(3) == 16.0


def test_retry_middleware_process_response_raises_on_retryable_status():
    middleware = RetryMiddleware(make_config())
    response = make_response(503)

    try:
        middleware.process_response(response)
        assert False, "aurait du lever RetryableResponseError"
    except RetryableResponseError as exc:
        assert exc.response is response


def test_retry_middleware_process_response_passes_through_on_success():
    middleware = RetryMiddleware(make_config())
    response = make_response(200)
    assert middleware.process_response(response) is response


def test_retry_middleware_process_request_is_passthrough():
    middleware = RetryMiddleware(make_config())
    headers = {"User-Agent": "x"}
    assert middleware.process_request("https://example.test/", headers) == ("https://example.test/", headers)


def test_parse_retry_after_absent_header_returns_none():
    response = make_response(429)
    assert RetryMiddleware._parse_retry_after(response) is None


def test_parse_retry_after_numeric_seconds():
    response = make_response(429, headers={"Retry-After": "42"})
    assert RetryMiddleware._parse_retry_after(response) == 42.0


def test_parse_retry_after_http_date():
    future = datetime.now(timezone.utc) + timedelta(seconds=120)
    response = make_response(429, headers={"Retry-After": format_datetime(future, usegmt=True)})

    delay = RetryMiddleware._parse_retry_after(response)

    assert delay is not None
    assert 110 <= delay <= 120


def test_parse_retry_after_invalid_value_returns_none():
    response = make_response(429, headers={"Retry-After": "pas-une-date-valide"})
    assert RetryMiddleware._parse_retry_after(response) is None
