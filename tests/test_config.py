import pytest

from dataharvest.config import Config

def test_file_not_found():
    """Vérifie qu'un fichier inexistant lève FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        Config("fichier_inexistant.yaml")

def test_missing_required_key(tmp_path):
    """Vérifie qu'une clé obligatoire manquante provoque une ValueError."""

    yaml_content = """
                        url: https://example.com
                        selectors:
                          titre: h2
                        fetcher:
                          delay: 1
                          retries: 3
                        store:
                          backend: csv
                          path: output.csv
                   """
    file = tmp_path / "config.yaml"
    file.write_text(yaml_content)

    with pytest.raises(ValueError):
        Config(file)


def test_valid_yaml(tmp_path):
    """ Vérifie le chargement correct d'un YAML valide."""

    yaml_content = """
                        url: https://example.com
                        pagination:
                          pattern: "?page={}"
                          start: 1
                          max_pages: 5
                        selectors:
                          titre: h2
                        fetcher:
                          delay: 1.5
                          retries: 3
                          timeout: 10
                          user_agent: test
                        store:
                          backend: csv
                          path: output.csv
                   """

    file = tmp_path / "config.yaml"
    file.write_text(yaml_content)

    config = Config(file)

    assert config.fetcher.delay == 1.5
    assert isinstance(config.fetcher.delay, float)