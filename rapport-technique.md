# DataHarvest -- Rapport technique

Mathieu & Navid
Master Dev, Data & IA -- 4eme annee -- IPSSI Montpellier
31 juillet 2026

---

## 1. Introduction et perimetre

*(A completer par le binome)*

- Quel probleme DataHarvest resout-il ?
- Quelles sont les limites de portee (ce qu'il ne fait pas intentionnellement) ?

### 1.1 Sites retenus pour les tests

5 sites ont ete retenus, couvrant 4 niveaux de difficulte differents parmi les 4 proposes par le sujet (qui exige au minimum 2) :

| Site | Niveau | Champs cibles |
|---|---|---|
| books.toscrape.com | 1 | titre, url, prix, disponibilite, note |
| quotes.toscrape.com | 1 | texte, auteur, tags |
| fr.wikipedia.org | 2 | wikitable ET infobox (listes, classements) |
| blogdumoderateur.com | 3 | titre, date, categorie |
| news.ycombinator.com | 4 | titre, url, score, domaine source, commentaires |

---

## 2. Architecture et choix de conception

*(A completer par le binome)*

- Pourquoi une architecture en composants decouples plutot qu'un script monolithique ?
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

### 2.2 Pourquoi BasePipeline est une ABC, et flat vs scope dans GenericPipeline

`BasePipeline` est une classe abstraite (`abc.ABC` avec `@abstractmethod`) plutot qu'une classe normale a methodes vides, pour une raison concrete et pas seulement stylistique : Python leve une `TypeError` a l'instanciation si `process()` ou `next_page_url()` n'est pas implementee, *avant meme* que le code tourne. Avec une classe normale a methodes vides (`def process(self): pass`), une pipeline concrete qui oublierait d'implementer `process()` heriterait silencieusement de la version vide -- elle renverrait `None` ou `[]` sans erreur, et le bug ne serait decouvert qu'en production, quand l'Orchestrator recevrait des donnees vides sans explication. L'ABC deplace l'erreur du runtime tardif au chargement du module : c'est une garantie donnee a quiconque ecrit une pipeline personnalisee, pas juste une convention documentee dans un commentaire.

Les deux implementations concretes, `GenericPipeline` et `PaginationPipeline`, illustrent aussi un choix de conception fait pendant le developpement plutot qu'anticipe des le depart. Le modele par defaut ("flat" : un selecteur CSS par champ applique a toute la page, items reconstruits en zippant les correspondances par position) est simple et suffit pour la majorite des sites testes (books.toscrape.com, quotes.toscrape.com, blogdumoderateur.com). Mais il echoue silencieusement -- sans exception, juste des donnees fausses -- des qu'un champ est present pour certains items et absent pour d'autres. Trouve concretement sur news.ycombinator.com : le domaine source (`span.sitestr`) n'existe que pour les stories avec lien externe (absent des posts "Ask HN"), ce qui volait le domaine d'une story a l'autre. Plutot que d'imposer partout le modele plus lourd (conteneur d'item scope, comme le fait Scrapy nativement), le mode flat est reste le defaut et un second mode optionnel (`item_selector`, chaque champ cherche dans son propre conteneur) n'a ete ajoute que la ou un site le demande reellement -- 1 site sur 5 (news.ycombinator.com) en a effectivement besoin. Illustration concrete du principe "ne pas batir la complexite avant d'en avoir la preuve".

### 2.3 Orchestrator : stockage par lot de pages et rapport de session

`Orchestrator.run()` sauvegarde les items valides page par page (`store.save(valides)` a chaque iteration de la boucle de pagination), plutot que d'accumuler tous les items de toutes les pages en memoire puis de sauvegarder en une seule fois a la fin. Deux raisons concretes : (1) si le scraping s'interrompt en cours de route (erreur reseau irrecuperable au milieu des `max_pages` pages), les pages deja traitees restent stockees au lieu d'etre perdues -- comportement explicitement demande par le sujet ("appeler store.save() par lot de pages") ; (2) ca borne l'empreinte memoire a une page a la fois plutot qu'a l'integralite du site, ce qui compte sur les sites a forte pagination (jusqu'a 50 pages sur books.toscrape.com).

Le rapport de session retourne par `run()` est un simple dict (pas une classe dediee) avec exactement les 6 cles demandees par le sujet -- `pages_scrapees`, `items_trouves`, `items_valides`, `items_rejetes`, `items_stockes`, `duree_secondes` -- construit par une methode privee `_build_report()` separee de la boucle principale : la logique de comptage (boucle de pagination) et la logique de mise en forme (rapport) restent independantes, chacune testable seule.

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

### 5.1 Difficultes rencontrees sur Pipeline (a completer par le reste du binome pour la retrospective globale)

- **Desalignement silencieux en mode flat** : le piege le plus subtil rencontre pendant le developpement. Sur l'infobox Wikipedia, un selecteur naif (`table.infobox tr td`) recuperait la valeur de la ligne d'en-tete (un `<td colspan="2">` sans `<th>` associe) au lieu de la premiere vraie ligne de donnees, decalant tout le reste d'un cran -- aucune exception levee, juste des donnees fausses. Corrige avec le combinateur CSS `+` (`th[scope='row'] + td`) pour forcer l'appariement ligne par ligne. Le meme type de bug a ete retrouve independamment sur news.ycombinator.com (domaine source absent de certains items), corrige cette fois via le nouveau mode `item_selector` (voir section 2.2).
- **Attributs `class` multi-valeurs** : sur books.toscrape.com, la note (`p.star-rating.Three`) encode l'information utile dans un deuxieme mot de l'attribut `class`, que BeautifulSoup retourne comme une liste Python plutot qu'une chaine. Le pipeline la rejoint en une seule chaine (`"star-rating Three"`) mais n'isole pas le mot utile ("Three") -- limite assumee et documentee dans les tests, pas corrigee (voir section 6 pour une piste).
- **Sites non scrapables statiquement** : legifrance.gouv.fr et numerama.com ont ete abandonnes apres verification reelle (curl sur le vrai HTML, pas une supposition) plutot qu'ecartes a priori.
  - *legifrance.gouv.fr* : sa page de recherche est une SPA Angular -- le HTML brut recupere par `requests` ne contient qu'un message `<noscript>Javascript est desactive...</noscript>`, aucun contenu exploitable sans executer le JavaScript. Des pages individuelles (`/codes/article_lc/...`) sont, elles, bien rendues cote serveur -- mais scraper une liste de resultats de recherche generique n'est pas possible avec l'approche statique de DataHarvest.
  - *numerama.com* : le sujet demande "titre, date, tags, nombre de commentaires". Verifie a la fois sur la page d'accueil ET sur une vraie page d'article (curl, sans JS) : aucun tag ni compteur de commentaires n'est present dans le HTML statique -- pas de JSON-LD, pas de widget Disqus/Coral cote serveur, probablement charges en JavaScript cote client si meme disponibles. Seuls titre/url/date auraient ete exploitables pour ce site avec l'approche statique de DataHarvest, ce qui ne couvre pas les champs demandes par le sujet.
- **Bug d'integration entre composants ecrits separement** : `Store.__init__` gardait le parametre `path` tel quel au lieu de le convertir en `Path`, alors que `save_csv`/`save_json` appellent `self.path.exists()` -- ca plantait des que `Store` recevait une simple string (le cas de `config.store.path`, venu du YAML). Corrige avec `self.path = Path(path)`, plus `self.path.parent.mkdir(parents=True, exist_ok=True)` (necessaire aussi car `output/` est gitignore, donc absent sur un clone frais).

*(Le reste de cette section -- retrospective globale, ce qu'on changerait, repartition des taches -- a completer une fois le framework termine.)*

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
