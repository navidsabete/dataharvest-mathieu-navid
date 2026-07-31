import pytest
from dataharvest.validator import Validator

def test_reject_missing_required_field():
    """Un item sans champ obligatoire est rejeté."""

    validator = Validator(required_fields=["titre", "url"])

    items = [
        {
            "titre": "Article"
        }
    ]

    valides, rejetes = validator.validate(items)

    assert valides == []
    assert len(rejetes) == 1


def test_reject_invalid_url():
    """Une URL invalide provoque un rejet."""

    validator = Validator(required_fields=["titre", "url"])
    items = [
        {
            "titre": "Article valide",
            "url": "mauvaise_url"
        }
    ]

    valides, rejetes = validator.validate(items)

    assert valides == []
    assert len(rejetes) == 1