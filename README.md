# DataHarvest

Framework de scraping modulaire -- projet final "Web Scraping", Master Dev, Data & IA, IPSSI Montpellier.

Le projet est construit autour d'une architecture en composants indépendants (Configuration, Fetcher, Pipeline, Validator, Store, Orchestrator) permettant de scraper différents sites à partir d'un simple fichier de configuration YAML/JSON.


---

# Architecture

```
                +------------------+
                |   Config (YAML)  |
                +--------+---------+
                         |
                         v
                 +---------------+
                 | Orchestrator  |
                 +---------------+
                  |    |    |    |
                  |    |    |    |
                  |    |    |    +--------------------+
                  |    |    |                         |
                  |    |    v                         v
                  |    | Validator -------------> Store
                  |    |
                  |    v
                  | Pipeline
                  |
                  v
               Fetcher
                  |
                  v
            Middleware chain
```
Flux de traitement :

```
Config
   |
   v
Fetcher (+ Middleware)
   |
   v
HTML
   |
   v
Pipeline
   |
   v
Items (list[dict])
   |
   v
Validator
   |
   +--> Rejetés (logs)
   |
   +--> Valides
          |
          v
        Store
```

---


# Installation

## Installation

```bash
git clone <repository>
cd <repository-folder>

python -m venv dataharvest_env

# Windows
.dataharvest_env\Scripts\activate

# Linux / macOS
source .dataharvest_env/bin/activate

pip install -r requirements.txt
```

---

# Utilisation

## Lancer un scraping

```bash
python -m dataharvest crawl --config configs/example_blog.yaml
```

Mode simulation (aucune donnée n'est stockée) :

```bash
python -m dataharvest crawl --config configs/example_blog.yaml --dry-run
```

## Exporter un backend

Exemple SQLite → CSV

```bash
python -m dataharvest export --from output/articles.db --to output/articles.csv
```

## Valider un fichier de configuration

```bash
python -m dataharvest validate --config configs/example_blog.yaml
```

---

# Modules implémentés

## `dataharvest/config.py`

Responsable du chargement de la configuration.

Fonctionnalités :
- chargement YAML (`.yaml`, `.yml`) ou JSON (`.json`) ;
- vérification de l'existence du fichier ;
- validation des clés obligatoires ;
- accès aux paramètres sous forme d'attributs (`config.fetcher.delay`) ;
- conservation de `selectors` sous forme de dictionnaire.

---

## `dataharvest/middleware.py`

Gestion de la chaîne de middlewares.

- `BaseMiddleware` : interface commune.
- `LoggingMiddleware` : journalisation des requêtes/réponses.
- `RetryMiddleware` :
  - gestion des erreurs HTTP 408 / 429 / 5xx ;
  - lecture de `Retry-After` ;
  - backoff exponentiel configurable.

---

## `dataharvest/fetcher.py`

Téléchargement des pages HTML.

Fonctionnalités :
- `requests.Session()` partagée ;
- passage dans la chaîne de middlewares ;
- gestion automatique des retries ;
- respect du délai entre les requêtes (`config.fetcher.delay`) ;
- utilisation du User-Agent défini dans la configuration.

---

## `dataharvest/pipeline.py`

Extraction des données HTML.

Deux implémentations :
- `GenericPipeline`
- `PaginationPipeline`

Fonctionnalités :
- extraction via sélecteurs CSS ;
- support `::text` et `::attr(...)` ;
- résolution des URLs relatives ;
- pagination automatique jusqu'à `max_pages`.

---

## `dataharvest/validator.py`

Validation des données avant stockage.

Fonctionnalités :
- vérification des champs obligatoires ;
- validation des URL ;
- contrôle optionnel de longueur minimale ;
- séparation des items valides et rejetés ;
- journalisation des éléments rejetés.

---

## `dataharvest/store.py`

Persistance des données.

Backends disponibles :
- CSV
- SQLite
- JSON

Fonctionnalités :
- sauvegarde des données ;
- comptage des éléments (`count()`) ;
- export entre différents backends (`export_to()`).

---

## `dataharvest/orchestrator.py`

Point central de l'application.

Il assemble automatiquement :
- Config
- Fetcher
- Middleware
- Pipeline
- Validator
- Store

`run()` :
- effectue la pagination ;
- valide les données ;
- stocke les résultats page par page ;
- retourne un rapport de session contenant :
  - pages_scrapees
  - items_trouves
  - items_valides
  - items_rejetes
  - items_stockes
  - duree_secondes

---

## `dataharvest/app.py`

Point d'entrée CLI.

Sous-commandes disponibles :
- `crawl`
- `export`
- `validate`

Fonctionnalités :
- chargement de la configuration ;
- mode `--dry-run` ;
- détection automatique du backend lors d'un export ;
- délégation du scraping à l'Orchestrator.

---

# Tests

Les tests sont réalisés avec **pytest**.

Tests unitaires implémentés :
- `test_config.py`
- `test_fetcher.py`
- `test_pipeline.py`
- `test_validator.py`
- `test_store.py`
- `test_orchestrator.py`
- `test_app.py`

Les tests couvrent les comportements critiques demandés dans l'énoncé.

Les tests d'intégration (`pytest.mark.integration`) permettent d'exécuter un scraping complet sur un site réel.

Lancement des tests :

```bash
pytest
```

Sans les tests d'intégration :

```bash
pytest -m "not integration"
```

Avec couverture :

```bash
pytest --cov=dataharvest --cov-report=term-missing -v
```

---

# État du projet

## À venir


---

## Auteurs

- Mathieu
- Navid