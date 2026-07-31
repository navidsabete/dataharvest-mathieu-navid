import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from dataharvest.app import build_parser, command_crawl, command_export, command_validate, detect_backend, main

def test_detect_backend_json():
    assert detect_backend("articles.json") == "json"

def test_detect_backend_csv():
    assert detect_backend("articles.csv") == "csv"

def test_detect_backend_sqlite_db():
    assert detect_backend("articles.db") == "sqlite"

def test_detect_backend_sqlite_extension():
    assert detect_backend("articles.sqlite") == "sqlite"

def test_detect_backend_unknown():
    with pytest.raises(ValueError):
        detect_backend("articles.xml")


def test_build_parser_returns_parser():
    parser = build_parser()
    assert parser is not None


def test_parser_crawl_command():
    parser = build_parser()
    args = parser.parse_args(["crawl", "--config", "configs/blog.yaml"])

    assert args.command == "crawl"
    assert args.config == "configs/blog.yaml"
    assert args.dry_run is False


def test_parser_crawl_dry_run():
    parser = build_parser()
    args = parser.parse_args(["crawl","--config", "configs/blog.yaml", "--dry-run"])

    assert args.command == "crawl"
    assert args.dry_run is True


def test_parser_export_command():
    parser = build_parser()
    args = parser.parse_args(["export", "--from", "articles.db", "--to", "articles.csv"])

    assert args.command == "export"
    assert args.source == "articles.db"
    assert args.target == "articles.csv"


def test_parser_validate_command():
    parser = build_parser()
    args = parser.parse_args(["validate", "--config", "configs/blog.yaml" ])

    assert args.command == "validate"
    assert args.config == "configs/blog.yaml"


def test_crawl_requires_config():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["crawl"])


def test_export_requires_arguments():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["export"])


def test_validate_requires_config():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["validate"])


def make_valid_config_file(tmp_path):
    yaml_content = """
url: https://example.com
pagination:
  pattern: null
  start: 1
  max_pages: 1
selectors:
  titre: h2
fetcher:
  delay: 1.0
  retries: 1
  timeout: 5
  user_agent: test
store:
  backend: json
  path: output.json
"""
    file = tmp_path / "config.yaml"
    file.write_text(yaml_content)
    return file


def test_command_validate_prints_success(tmp_path, capsys):
    config_file = make_valid_config_file(tmp_path)
    command_validate(SimpleNamespace(config=str(config_file)))

    captured = capsys.readouterr()
    assert "Configuration valide" in captured.out


def test_command_export_calls_store_export_to(tmp_path, capsys):
    source = tmp_path / "data.json"
    source.write_text(json.dumps([{"titre": "A", "url": "https://example.com/a"}]), encoding="utf-8")
    target = tmp_path / "data.csv"

    command_export(SimpleNamespace(source=str(source), target=str(target)))

    captured = capsys.readouterr()
    assert "1 items exportés" in captured.out
    assert target.exists()


def test_command_crawl_dry_run_does_not_call_orchestrator_run():
    args = SimpleNamespace(config="configs/books_toscrape.yaml", dry_run=True)

    fake_orchestrator = MagicMock()
    fake_orchestrator.fetcher.fetch.return_value = "<html></html>"
    fake_orchestrator.pipeline.process.return_value = [{"titre": "X"}]

    with patch("dataharvest.app.Config"), patch("dataharvest.app.Orchestrator", return_value=fake_orchestrator):
        command_crawl(args)

    fake_orchestrator.run.assert_not_called()
    fake_orchestrator.fetcher.fetch.assert_called_once()


def test_command_crawl_full_run_prints_report(capsys):
    args = SimpleNamespace(config="configs/books_toscrape.yaml", dry_run=False)

    fake_orchestrator = MagicMock()
    fake_orchestrator.run.return_value = {
        "pages_scrapees": 1,
        "items_trouves": 2,
        "items_valides": 2,
        "items_rejetes": 0,
        "items_stockes": 2,
        "duree_secondes": 0.5,
    }

    with patch("dataharvest.app.Config"), patch("dataharvest.app.Orchestrator", return_value=fake_orchestrator):
        command_crawl(args)

    captured = capsys.readouterr()
    assert "Items stockes  : 2" in captured.out
    fake_orchestrator.run.assert_called_once()


def test_main_dispatches_to_crawl(monkeypatch):
    monkeypatch.setattr("sys.argv", ["dataharvest", "crawl", "--config", "configs/books_toscrape.yaml"])
    with patch("dataharvest.app.command_crawl") as mocked:
        main()
    mocked.assert_called_once()


def test_main_dispatches_to_export(monkeypatch):
    monkeypatch.setattr("sys.argv", ["dataharvest", "export", "--from", "a.json", "--to", "b.csv"])
    with patch("dataharvest.app.command_export") as mocked:
        main()
    mocked.assert_called_once()


def test_main_dispatches_to_validate(monkeypatch):
    monkeypatch.setattr("sys.argv", ["dataharvest", "validate", "--config", "configs/books_toscrape.yaml"])
    with patch("dataharvest.app.command_validate") as mocked:
        main()
    mocked.assert_called_once()


def test_main_prints_help_without_command(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["dataharvest"])
    main()

    captured = capsys.readouterr()
    assert "usage" in captured.out.lower()