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


def test_csv_save_and_count(tmp_path):
    file = tmp_path / "data.csv"
    store = Store("csv", file)

    assert store.save([]) == 0  # save_csv sur liste vide
    assert store.count() == 0  # count() csv, fichier absent

    count = store.save([{"titre": "A", "url": "https://example.com/a"}])
    assert count == 1
    assert store.count() == 1

    # deuxieme sauvegarde : pas de nouvel en-tete ecrit
    store.save([{"titre": "B", "url": "https://example.com/b"}])
    assert store.count() == 2


def test_json_count_when_file_absent(tmp_path):
    store = Store("json", tmp_path / "absent.json")
    assert store.count() == 0


def test_sqlite_save_empty_items(tmp_path):
    store = Store("sqlite", tmp_path / "data.db")
    assert store.save([]) == 0


def test_load_all_csv(tmp_path):
    file = tmp_path / "data.csv"
    store = Store("csv", file)
    store.save([{"titre": "A", "url": "https://example.com/a"}])

    assert store.load_all() == [{"titre": "A", "url": "https://example.com/a"}]


def test_load_all_csv_when_file_absent(tmp_path):
    store = Store("csv", tmp_path / "absent.csv")
    assert store.load_all() == []


def test_load_all_json_when_file_absent(tmp_path):
    store = Store("json", tmp_path / "absent.json")
    assert store.load_all() == []


def test_load_all_sqlite(tmp_path):
    file = tmp_path / "data.db"
    store = Store("sqlite", file)
    store.save([{"titre": "A", "url": "https://example.com/a"}])

    items = store.load_all()
    assert len(items) == 1
    # sqlite ajoute sa propre colonne "id" (AUTOINCREMENT) en plus des champs sauvegardes
    assert items[0]["titre"] == "A"
    assert items[0]["url"] == "https://example.com/a"