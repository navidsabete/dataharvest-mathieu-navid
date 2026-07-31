import json
from dataharvest.store import Store

def test_json_save(tmp_path):
    file = tmp_path / "data.json"
    store = Store("json", file)
    items = [
        {
            "titre": "Article",
            "url": "https://example.com"
        }
    ]
    count = store.save(items)
    assert count == 1
    assert file.exists()

    with open(file, encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1


def test_sqlite_no_duplicate_url(tmp_path):
    file = tmp_path / "data.db"
    store = Store("sqlite", file)
    item = {
        "titre": "Article",
        "url": "https://example.com"
    }
    count = store.save(
        [
            item,
            item
        ]
    )

    assert count == 1
    assert store.count() == 1


def test_export_json_to_sqlite(tmp_path):
    json_file = tmp_path / "data.json"
    sqlite_file = tmp_path / "data.db"
    source = Store("json", json_file)
    source.save(
        [
            {
                "titre": "Article",
                "url": "https://example.com"
            }
        ]
    )

    exported = source.export_to("sqlite", sqlite_file)
    assert exported == 1

    target = Store("sqlite", sqlite_file)
    assert target.count() == 1

def test_unknown_backend(tmp_path):
    try:
        Store("xml", tmp_path / "data.xml")
        assert False
    except ValueError:
        assert True