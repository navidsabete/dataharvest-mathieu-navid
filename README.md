# DataHarvest

Framework de scraping modulaire -- projet final "Web Scraping", Master Dev, Data & IA, IPSSI Montpellier.

## Implementé pour l'instant

### `dataharvest/config.py`

- Chargement automatique d'un fichier **YAML** (`.yaml` , `.yml`) ou **JSON** (`.json`) selon son extension.
- Vérification de l'existence du fichier (`FileNotFoundError`).
- Validation de la présence des clés obligatoires (`ValueError` si une clé est absente).
- Conversion récursive des dictionnaires en objets afin d'accéder aux paramètres -sous forme d'attributs (`config.fetcher.delay`).
- Conservation de `selectors` sous forme de dictionnaire afin de permettre un nombre variable de champs à extraire.

### `dataharvest/validator.py`

- Vérification de la présence des champs obligatoires.
- Validation du format des URL (HTTP/HTTPS avec domaine).
- Vérification optionnelle d'une longueur minimale pour certains champs.
- Séparation des éléments en deux listes :
    - items valides ;
    - items rejetés.
- Journalisation (`logging.WARNING`) de chaque élément rejeté.

### `dataharvest/store.py`

**Backends supportés : CSV + SQLite + JSON**

### `dataharvest/app.py`

Il constitue le point d'entrée du projet.

Il utilise `argparse` afin de proposer une interface en ligne de commande composée de trois sous-commandes :
- `crawl`
- `export`
- `validate`

**Fonctionnalités**
- chargement de la configuration
- détection automatique du backend lors d'un export
- prise en charge de l'option `--dry-run` 
- délégation de l'exécution du scraping à l'`Orchestrator`

### `dataharvest/middleware.py`

- `BaseMiddleware` (ABC) : interface `process_request(url, headers)` / `process_response(response)`, implementee par chaque middleware concret.
- `LoggingMiddleware` : logge chaque requete (`[GET url]`) et sa reponse (`[200 OK - 1.23s]`), temps mesure avec `time.perf_counter()`.
- `RetryMiddleware` : detecte les statuts 408/429/5xx (`RETRYABLE_STATUS_CODES`) et leve `RetryableResponseError`. Pour un 429 (ou tout statut retryable), lit l'en-tete HTTP `Retry-After` (secondes ou date HTTP) et le transmet ; sinon expose le calcul du backoff exponentiel `base_delay * (2 ** attempt)` via `backoff_delay()`.

### `dataharvest/fetcher.py`

- `Fetcher` : telecharge le HTML via une `requests.Session()` partagee, fait passer chaque requete/reponse dans toute la chaine de middlewares (dans l'ordre d'ajout).
- Retry avec backoff sur erreurs reseau et statuts 408/429/5xx ; leve `FetchError` apres epuisement des tentatives.
- Sur un statut HTTP definitif non retryable (ex : 404, 403), leve `FetchError` immediatement sans gaspiller de tentatives.
- Si le serveur fournit `Retry-After` (typiquement sur 429), ce delai prime sur le backoff calcule.
- Chaque tentative ratee est loggee explicitement : `[RETRY url - detail - prochaine tentative dans Xs]` (URL, code HTTP ou type d'exception, delai).
- `fetch_all()` respecte `config.fetcher.delay` entre chaque URL.
- User-Agent toujours pris depuis la config (`config.fetcher.user_agent`), jamais le defaut Python.

#### Deux delais distincts, a ne pas confondre

| | Source | Role |
|---|---|---|
| `config.fetcher.delay` | YAML, cle obligatoire validee par `Config` | Espacement entre deux URLs differentes (`fetch_all()`) |
| `RetryMiddleware.base_delay` | Defaut Python (`1.0`) dans `middleware.py`, jamais lu depuis le YAML | Base du backoff exponentiel quand on retry une meme URL (`base * 2^attempt`) |

Le sujet (section 4.2) ne demande de rendre configurable que `max_retries` pour `RetryMiddleware` -- c'est fait via `config.fetcher.retries`. `base_delay` reste un defaut de code, pas une cle YAML.

#### Verifications manuelles effectuees (mocks, hors reseau reel)

- **429 avec `Retry-After: 2`** -> respecte les 2s du serveur, pas de calcul (meme avec un `base_delay` different).
- **500 sans `Retry-After`** -> retombe sur le backoff exponentiel (`0.01s`, `0.02s`, ...).
- **Erreur reseau (`ConnectionError`)** -> backoff exponentiel egalement, type d'exception loggue.
- **404** -> `FetchError` immediat, sans passer par la boucle de retry.

### `dataharvest/pipeline.py`

- `BasePipeline` (ABC) : interface `process(html)` / `next_page_url(html, current_url)`.
- `GenericPipeline(selectors, base_url="", item_selector=None)` : extrait des items depuis du HTML brut a partir de selecteurs CSS. Deux modes :
  - **flat** (par defaut, `item_selector` non fourni) : un selecteur par champ applique a toute la page, items reconstruits en zippant les correspondances par position. Simple, mais suppose qu'un champ apparait au plus une fois par item -- un champ absent pour certains items seulement decale les suivants.
  - **scope** (`item_selector` fourni) : chaque champ est cherche a l'interieur de son propre conteneur d'item, avec repli sur l'element suivant immediat s'il n'y est pas (utile pour les sites qui etalent un item sur deux elements adjacents). Evite le desalignement quand un champ est optionnel selon les items.
  - Support `::attr(nom)` / `::text` en suffixe de selecteur (syntaxe inspiree de Scrapy) pour cibler un attribut plutot que le texte visible.
  - URLs relatives resolues via `base_url` ; aucune exception si un selecteur ne trouve rien (chaine vide).
- `PaginationPipeline(selectors, pagination_config, base_url="", item_selector=None)` : etend `GenericPipeline`, construit l'URL de la page suivante via `pagination_config.pattern.format(n=...)`, s'arrete a `max_pages` ou des qu'une page ne contient plus d'items.

Teste avec du vrai HTML capture (curl, pas invente) sur les 5 sites cibles retenus, couvrant 4 niveaux de difficulte differents (contrainte de diversite du sujet respectee) :

| Site | Niveau | Champs |
|---|---|---|
| books.toscrape.com | 1 | titre, url, prix, disponibilite, note |
| quotes.toscrape.com | 1 | texte, auteur, tags |
| fr.wikipedia.org | 2 | wikitable ET infobox |
| blogdumoderateur.com | 3 | titre, date, categorie |
| news.ycombinator.com | 4 | titre, url, score, domaine, commentaires |

Details des pieges reels trouves par site (alignement des champs optionnels, attributs `class` multi-valeurs, structure en deux lignes...) dans `tests/test_pipeline.py` et `tests/test_pipeline_real_sites.py`.

### `dataharvest/config.py`, `validator.py`, `store.py` (Navid)

`Config` (chargement YAML/JSON, validation des cles obligatoires), `Validator` (champs requis, URL, longueur min) et `Store` (backends csv/sqlite/json + `export_to()`) sont implementes, avec tests (`tests/test_config.py`, `tests/test_validator.py`, `tests/test_store.py`).

### `dataharvest/orchestrator.py`

- `Orchestrator(config)` : assemble `Fetcher` (avec `LoggingMiddleware` + `RetryMiddleware`), `PaginationPipeline` (avec `base_url=config.url`, indispensable pour resoudre les URLs relatives extraites par le pipeline), `Validator(required_fields=['titre', 'url'])` et `Store` -- conforme au pseudo-code impose section 4.7.
- `run()` : boucle de pagination automatique via `pipeline.next_page_url()`, valide et **stocke par lot de pages** (chaque page sauvegardee des qu'elle est traitee, pas tout accumule puis ecrit a la fin). Retourne un rapport (dict) avec exactement les 6 cles demandees : `pages_scrapees`, `items_trouves`, `items_valides`, `items_rejetes`, `items_stockes`, `duree_secondes`.
- Teste avec un `Fetcher` dont la session `requests` est mockee sur 2 pages (pas de reseau reel) : verifie les 6 cles du rapport, le comptage sur plusieurs pages, le rejet d'un item avec URL invalide, et le stockage cumulatif (`tests/test_orchestrator.py`).


## TODO:() A venir

configs reelles des 5 sites (`configs/*.yaml`), `tests/test_integration.py`.

## Tests unitaires

Les tests ont été réalisés avec `pytest` et couvrent les comportements critiques demandés par le sujet.

`app.py` étant le point d'entrée du projet, il était pertinent d'ajouter une couverture de tests pour ce module avant de pouvoir intéragir avec l'app

## Auteurs

- Mathieu
- Navid