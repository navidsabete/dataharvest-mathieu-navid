# dataharvest-mathieu-navid

Framework de scraping modulaire -- projet final "Web Scraping", Master Dev, Data & IA, IPSSI Montpellier.

## Implemente pour l'instant

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

## A venir

`config.py`, `pipeline.py`, `validator.py`, `store.py`, `orchestrator.py`, `app.py`, tests, configs des sites.

## Auteurs

- Mathieu
- Navid
