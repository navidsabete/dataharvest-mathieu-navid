# DataHarvest -- Rapport technique

Mathieu & Navid
Master Dev, Data & IA -- 4eme annee -- IPSSI Montpellier
31 juillet 2026

---

## 1. Introduction et perimetre

*(A completer par le binome)*

- Quel probleme DataHarvest resout-il ?
- Quelles sont les limites de portee (ce qu'il ne fait pas intentionnellement) ?
- Quel site avez-vous choisi pour tester ? Pourquoi ?

---

## 2. Architecture et choix de conception

*(A completer par le binome)*

- Pourquoi une architecture en composants decouples plutot qu'un script monolithique ?
- Pourquoi BasePipeline est-elle une classe abstraite (ABC) et pas une classe normale avec des methodes vides ?
- Pourquoi le chargement de configuration via YAML plutot que des arguments CLI ?
- Pourquoi l'injection de dependances dans le constructeur plutot que des imports directs ?

### 2.1 Pourquoi le pattern middleware pour le Fetcher, et gestion du retry

Le retry est deliberement scinde en deux responsabilites, reparties de part et d'autre du pattern middleware :

- `RetryMiddleware` (`middleware.py`) decide *si* une reponse ou une exception doit declencher un nouvel essai (statuts 408/429/5xx, exceptions reseau) et calcule *le delai a respecter* -- l'en-tete HTTP `Retry-After` renvoye par le serveur quand il est present (typiquement sur un 429), sinon un backoff exponentiel `base_delay * 2^attempt`.
- `Fetcher.fetch()` reste seul responsable de la boucle elle-meme : comptage des tentatives, `time.sleep()`, abandon final via `FetchError`.

Sans ce pattern, la politique de retry (quels codes retenter, comment lire `Retry-After`) serait codee en dur dans `Fetcher`, qui deviendrait responsable a la fois du transport HTTP et de la decision de retry -- impossible a tester ou remplacer independamment. Avec le pattern, `RetryMiddleware.process_response()` se teste seul (statut -> exception levee ou non, delai calcule) sans jamais ouvrir de connexion reseau.

Deux delais independants coexistent dans le code et ne doivent pas etre confondus :

| Parametre | Source | Role |
|---|---|---|
| `config.fetcher.delay` | YAML, cle obligatoire validee par `Config` | Espacement entre deux URLs differentes, dans `fetch_all()` |
| `RetryMiddleware.base_delay` | Defaut Python (`1.0`), jamais lu depuis le YAML | Base du backoff exponentiel entre deux tentatives sur la *meme* URL |

Le sujet (section 4.2) ne demande de rendre configurable que `max_retries` pour `RetryMiddleware` -- fait via `config.fetcher.retries` -- et non le `base_delay` du backoff, qui reste donc un defaut de code plutot qu'une cle YAML.

**Verifications effectuees** (via `unittest.mock`, sans dependre du reseau reel) :

- 429 avec en-tete `Retry-After: 2` -> le delai fourni par le serveur est respecte tel quel, meme avec un `base_delay` de calcul different (5.0s) : le backoff calcule n'est pas utilise dans ce cas.
- 500 sans `Retry-After` -> retombe sur le backoff exponentiel (`0.01s`, puis `0.02s` sur les tentatives suivantes).
- Exception reseau (`requests.ConnectionError`) -> meme comportement de backoff exponentiel, avec le type d'exception journalise a chaque tentative.
- 404 -> `FetchError` levee immediatement, sans passer par la boucle de retry (statut definitif, hors `RETRYABLE_STATUS_CODES`).

---

## 3. Comparaison avec Scrapy

### 3.1 Fonctionnalites que Scrapy offre et que DataHarvest n'offre pas

**1. Moteur asynchrone (Twisted, `CONCURRENT_REQUESTS`)**
Scrapy traite plusieurs requetes en parallele sans bloquer le thread principal. DataHarvest est volontairement synchrone (un seul thread, `requests.Session` bloquant) : implementer un moteur asynchrone complet (event loop, ordonnancement des coroutines, backpressure) depasse largement le budget de 5h et n'etait pas l'objectif pedagogique du projet, qui porte sur l'architecture par composants et non sur la reimplementation d'un moteur reseau asynchrone.

**2. Cache HTTP disque (`HttpCacheMiddleware`)**
Permet de rejouer un scraping sans re-solliciter le reseau, utile en developpement pour iterer rapidement sur les selecteurs. Non implemente : bon candidat d'evolution future (voir section 6), mais ajoute de la complexite (invalidation, serialisation) hors scope du sujet initial.

**3. Rotation de User-Agent / pool de proxies (`scrapy-user-agents`, `scrapy-rotating-proxies`)**
Ecarte volontairement, pas seulement par manque de temps : ces mecanismes servent a contourner la detection anti-bot des sites, ce qui contredit l'exigence d'un User-Agent identifiable posee en section 4 (ethique) et l'esprit "bon citoyen du web" du projet. Notre Fetcher utilise au contraire un unique User-Agent identifiable, fourni par la configuration.

**4. Rendu JavaScript (`scrapy-playwright`, Splash)**
DataHarvest cible explicitement le HTML statique (cf. perimetre, section 1). Ajouter un moteur de rendu JS changerait la nature de l'outil et sortirait du perimetre defini par le sujet.

**5. Export "feed" declaratif multi-format en une option CLI (`-o out.json`)**
Scrapy ecrit vers plusieurs formats simultanement sans code supplementaire. `Store.export_to()` couvre notre besoin de conversion entre backends (csv/sqlite/json), mais pas l'ecriture simultanee vers N formats en une seule commande : complexite jugee non prioritaire vu le temps imparti.

### 3.2 Dans quels cas preferer DataHarvest a Scrapy ?

**Scenario 1 -- integration dans une application existante.** Un developpeur qui a deja un script Python (ETL, notebook, tache cron) et veut ajouter un scraping ponctuel sans faire entrer Twisted, et son modele de programmation asynchrone specifique, dans ses dependances peut importer directement `Orchestrator` comme une classe Python normale et bloquante, sans reacteur a demarrer ni arreter.

**Scenario 2 -- contexte pedagogique ou script jetable.** Pour scraper cinq pages une seule fois, ou dans un cadre etudiant ou l'objectif est de comprendre chaque etape de la chaine (fetch -> parse -> valider -> stocker), un outil d'une dizaine de fichiers lisibles de bout en bout en quelques minutes est preferable a l'apprentissage de toute la surface de configuration de Scrapy (`settings.py`, signals, items, spiders, middlewares empiles).

### 3.3 Impact synchrone vs asynchrone -- calcul theorique (100 pages, DOWNLOAD_DELAY=1s)

Hypotheses : delai configure de 1s entre requetes, temps moyen reseau + traitement par page t_req ~= 0.3s, Scrapy avec sa concurrence par defaut `CONCURRENT_REQUESTS_PER_DOMAIN = 8`.

**DataHarvest (synchrone).** Chaque requete attend la fin de la precedente :

```
temps_total ~= N x (delay + t_req)
            = 100 x (1 + 0.3)
            = 130 s  (~2 min 10)
```

**Scrapy (asynchrone, concurrence C = 8).** Jusqu'a 8 requetes en vol simultanement, le delai s'applique par slot de concurrence et non de facon strictement sequentielle :

```
temps_total ~= (N / C) x (delay + t_req)
            = (100 / 8) x 1.3
            ~= 16,25 s
```

Soit un gain theorique d'environ **8x** pour Scrapy sur ce volume, l'ecart se creusant encore a mesure que le nombre de pages augmente. A l'echelle de ce projet (5 sites de quelques dizaines de pages chacun), l'ecart reste de l'ordre de quelques dizaines de secondes contre quelques secondes -- non bloquant pour notre usage -- mais deviendrait significatif au-dela de quelques centaines de pages ou de plusieurs domaines scrapes en parallele.

---

## 4. Cadre legal et ethique

*(A completer par le binome)*

- Analysez le robots.txt du site que vous avez scrape. Quelles URL etaient interdites ? Les avez-vous respectees ?
- Quelle base legale (RGPD Art. 6) justifie votre collecte de donnees ?
- Les donnees collectees sont-elles des donnees personnelles ? Argumentez.
- Quels mecanismes techniques DataHarvest met-il en place pour etre un "bon citoyen" du web (throttling, User-Agent identifiable, UNIQUE url, etc.) ?

---

## 5. Difficultes et retrospective

*(A completer par le binome)*

- Quelle a ete la difficulte technique principale ? Comment l'avez-vous resolue ?
- Qu'est-ce que vous referiez differemment si vous recommenciez ?
- Quelle fonctionnalite n'avez-vous pas eu le temps d'implementer ? Comment l'implementeriez-vous ?
- Repartition des taches : qui a fait quoi ? Est-ce que cela se voit dans Git ?

---

## 6. Perspectives

*(A completer par le binome)*

- Proposez une 6e brique pour DataHarvest (ex : Notifier, Scheduler, Monitor). Decrivez son interface en pseudo-code Python.
- Comment rendriez-vous DataHarvest compatible avec les sites JavaScript sans dependre de Selenium ? (indice : Playwright, splash, pre-rendering)
- Que faudrait-il ajouter pour distribuer DataHarvest sur PyPI ?

---

## Bibliographie

- Documentation Scrapy -- Architecture overview, RetryMiddleware, HttpCacheMiddleware, AutoThrottle : https://docs.scrapy.org/
- Documentation requests / urllib3 -- gestion des sessions et de la decompression HTTP.
