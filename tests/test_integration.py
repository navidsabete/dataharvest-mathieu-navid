"""Test d'integration obligatoire (section 5 du sujet) : bout en bout, vrai
reseau, aucun mock. Necessite une connexion internet -- exclu par defaut avec
`pytest -m "not integration"`, lance explicitement avec `pytest -m integration`."""

from pathlib import Path

import pytest

from dataharvest.config import Config
from dataharvest.orchestrator import Orchestrator


@pytest.mark.integration
def test_orchestrator_run_end_to_end_on_real_site():
    config = Config("configs/example_blog.yaml")
    orchestrator = Orchestrator(config)

    report = orchestrator.run()

    assert report["items_stockes"] >= 5

    output_path = Path(config.store.path)
    assert output_path.exists()
    assert output_path.stat().st_size > 0
