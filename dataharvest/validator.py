import logging

logger = logging.getLogger(__name__)

class Validator:
    """Valide les données extraites avant stockage.
    Exemple :
        validator = Validator(required_fields=["titre", "url"], min_lengths={"titre": 5})
        valides, rejetes = validator.validate(items)
    """

    def __init__(self, required_fields: list[str], min_lengths: dict = None):
        self.required_fields = required_fields
        self.min_lengths = min_lengths or {}

    def validate(self, items: list[dict]) -> tuple[list[dict], list[dict]]:
        """Retourne (valides, rejetes)."""

        valides = []
        rejetes = []

        for item in items:
            if self.is_valid_item(item):
                valides.append(item)
            else:
                logger.warning(f"Item rejeté : {item}")
                rejetes.append(item)

        return valides, rejetes

    def is_valid_item(self, item: dict) -> bool:
        """Vérifie toutes les règles de validation.
        Exemple :
                Si min_lengths est fourni, ex : {'titre': 5}, les items avec titre de moins de 5 caracteres sont rejetes
        """
        # Vérification des champs obligatoires
        for field in self.required_fields:
            if (field not in item or item[field] is None  or str(item[field]).strip() == ""):
                return False

        if "url" in item:
            if not self.is_valid_url(item["url"]):
                return False
            
        for field, minimum in self.min_lengths.items():
            if field in item:
                if len(str(item[field])) < minimum:
                    return False
        return True

    def is_valid_url(self, url: str) -> bool:
        """True si l'URL commence par http(s):// et contient un domaine."""

        if not isinstance(url, str):
            return False

        url = url.strip()

        if not (url.startswith("http://") or url.startswith("https://")):
            return False

        domain = url.split("://", 1)[1]

        return bool(domain and "." in domain and not domain.startswith("."))