from pathlib import Path
import json, yaml

class ConfigNode:
    """Transforme récursivement un dictionnaire en objet accessible par attribut."""

    def __init__(self, data: dict):
        for key, value in data.items():
            if isinstance(value, dict) and key != "selectors":
                value = ConfigNode(value)
            setattr(self, key, value)

class Config(ConfigNode):
    """Charge un fichier YAML ou JSON et expose les paramètres sous forme d'attributs.
    Exemples :
        config.fetcher.delay
        config.store.backend
        config.selectors["titre"]
    """

    REQUIRED_KEYS = ["url","pagination","selectors","fetcher","store"]

    def __init__(self, filename: str):
        path = Path(filename)

        if not path.exists():
            raise FileNotFoundError(f"Configuration introuvable : {filename}")

        self.data = self.load_file(path)
        self.validate(self.data)
        super().__init__(self.data)

    @staticmethod
    def load_file(path: Path) -> dict:
        """Charge un fichier YAML ou JSON."""
        suffix = path.suffix.lower()
        with open(path, "r", encoding="utf-8") as f:
            if suffix in (".yaml", ".yml"):
                return yaml.safe_load(f)
            if suffix == ".json":
                return json.load(f)
        raise ValueError(
            "Format de configuration non supporté "
            "(extensions autorisées : .yaml, .yml, .json)"
        )

    def validate(self, data: dict):
        """Vérifie la présence des clés obligatoires."""

        missing = [
            key for key in self.REQUIRED_KEYS
            if key not in data
        ]

        if missing:
            raise ValueError(f"Clés obligatoires manquantes : {', '.join(missing)}")

        # Vérification de types
        if not isinstance(data["selectors"], dict):
            raise ValueError("'selectors' doit être un dictionnaire")

        try:
            data["fetcher"]["delay"] = float(data["fetcher"]["delay"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("'fetcher.delay' doit être un nombre")
    