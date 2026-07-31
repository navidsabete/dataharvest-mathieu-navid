import pytest
from dataharvest.app import build_parser, detect_backend

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