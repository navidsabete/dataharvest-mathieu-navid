"""Tests de GenericPipeline/PaginationPipeline avec des extraits HTML reels,
calques sur le vrai HTML capture via curl le 2026-07-31 (pas invente).

5 sites cibles retenus pour le projet (2 niveaux differents minimum, ici 4) :
books.toscrape.com, quotes.toscrape.com et fr.wikipedia.org (niveaux 1-2),
blogdumoderateur.com et news.ycombinator.com (niveaux 3-4). numerama.com et
legifrance.gouv.fr ont ete ecartes : voir l'historique du depot pour le detail
des blocages trouves (JS necessaire pour l'un, champs absents pour l'autre).

Couverture par rapport aux champs demandes section 2 du sujet :
- books.toscrape.com   : titre (complet, via ::attr(title)), url, prix,
                          disponibilite, note (limite : mot "Three" non isole
                          d'un attribut class multi-valeurs).
- quotes.toscrape.com  : texte, auteur, tags (via meta[content], evite le
                          desalignement des <a class="tag"> multiples).
- fr.wikipedia.org     : wikitable (listes/classements) ET infobox, les deux
                          demandes par le sujet -- l'infobox a un piege reel
                          d'alignement documente dans les tests.
- blogdumoderateur.com : titre, date (via ::attr(datetime)), categorie --
                          choisi comme "le plus simple" parmi 6 candidats
                          niveau 3 apres verification curl de chacun : 44
                          <article> pour 44 <time>, comptage exact, classes
                          non-obfusquees (WordPress classique). Les candidats
                          ecartes : clubic.com (app Next.js, 0 <article> dans
                          le HTML statique -- quasi inutilisable sans JS),
                          lesnumeriques.com (classes tres imbriquees/verboses),
                          01net/lemondeinformatique/silicon.fr (corrects mais
                          moins propres). "chapeau" (4e champ demande par le
                          sujet) est ABSENT des cartes de la page d'accueil,
                          meme limite que numerama pour les commentaires.
- news.ycombinator.com : titre, url, score, commentaires -- choisi comme le
                          plus simple parmi 3 candidats niveau 4 (30 <tr
                          class="athing"> pour 30 <span class="score"> et 30
                          <span class="sitestr">, alignement parfait, HTML
                          quasi inchange depuis 15 ans). Ecartes : github.com
                          /trending (page correcte mais 626 Ko pour 14 repos,
                          tres verbeux), old.reddit.com (structure correcte
                          mais legerement moins reguliere). Deux vrais pieges
                          trouves en testant : (1) le lien du domaine source
                          est IMBRIQUE dans .titleline, donc un selecteur
                          "span.titleline a" (descendant) capture aussi ce
                          lien en trop -- il faut ">" (enfant direct) ; (2)
                          <span class="sitestr"> n'existe QUE pour les
                          stories avec lien externe (absent des Ask HN), donc
                          le mode "flat" par defaut DESALIGNE le champ
                          "domaine" des qu'une story sans domaine apparait --
                          corrige via le nouveau mode item_selector de
                          GenericPipeline (voir pipeline.py), qui scope
                          chaque champ a son conteneur (avec repli sur le
                          <tr> suivant, car score/commentaires vivent dans
                          la ligne "subtext" separee du <tr class="athing">)."""

from types import SimpleNamespace

from dataharvest.pipeline import GenericPipeline, PaginationPipeline

# ---------------------------------------------------------------------------
# books.toscrape.com -- Niveau 1
# ---------------------------------------------------------------------------

BOOKS_SELECTORS = {
    "titre": "h3 a::attr(title)",
    "url": "h3 a::attr(href)",
    "prix": "p.price_color",
    "disponibilite": "p.instock.availability",
    "note": "p.star-rating::attr(class)",
}

BOOKS_HTML = """
<html><body>
<article class="product_pod">
    <div class="image_container">
        <a href="catalogue/a-light-in-the-attic_1000/index.html">
            <img src="media/a.jpg" alt="A Light in the Attic" class="thumbnail">
        </a>
    </div>
    <p class="star-rating Three">
        <i class="icon-star"></i><i class="icon-star"></i><i class="icon-star"></i>
    </p>
    <h3><a href="catalogue/a-light-in-the-attic_1000/index.html" title="A Light in the Attic">A Light in the ...</a></h3>
    <div class="product_price">
        <p class="price_color">£51.77</p>
        <p class="instock availability"><i class="icon-ok"></i> In stock</p>
    </div>
</article>
<article class="product_pod">
    <div class="image_container">
        <a href="catalogue/tipping-the-velvet_999/index.html">
            <img src="media/b.jpg" alt="Tipping the Velvet" class="thumbnail">
        </a>
    </div>
    <p class="star-rating One">
        <i class="icon-star"></i>
    </p>
    <h3><a href="catalogue/tipping-the-velvet_999/index.html" title="Tipping the Velvet">Tipping the Velvet</a></h3>
    <div class="product_price">
        <p class="price_color">£53.74</p>
        <p class="instock availability"><i class="icon-ok"></i> In stock</p>
    </div>
</article>
</body></html>
"""


def test_books_toscrape_extracts_full_title_via_attr_suffix():
    # Le texte visible du <h3><a> est tronque ("A Light in the ..."), le titre
    # complet est dans l'attribut title -> d'ou le ::attr(title) explicite.
    pipeline = GenericPipeline(BOOKS_SELECTORS, base_url="https://books.toscrape.com/")
    items = pipeline.process(BOOKS_HTML)

    assert len(items) == 2
    assert items[0]["titre"] == "A Light in the Attic"
    assert items[0]["url"] == "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    assert items[0]["prix"] == "£51.77"
    assert items[0]["disponibilite"] == "In stock"
    # Limite connue : la note est dans un attribut class multi-valeurs
    # ("star-rating Three") ; l'isolement du mot ("Three") demanderait un
    # post-traitement specifique que le pipeline generique ne fait pas.
    assert items[0]["note"] == "star-rating Three"
    assert items[1]["titre"] == "Tipping the Velvet"


def test_books_toscrape_pagination_pattern():
    pagination_config = SimpleNamespace(pattern="catalogue/page-{n}.html", start=1, max_pages=50)
    pipeline = PaginationPipeline(BOOKS_SELECTORS, pagination_config, base_url="https://books.toscrape.com/")

    next_url = pipeline.next_page_url(BOOKS_HTML, "https://books.toscrape.com/index.html")
    assert next_url == "https://books.toscrape.com/catalogue/page-2.html"


# ---------------------------------------------------------------------------
# quotes.toscrape.com -- Niveau 1
# ---------------------------------------------------------------------------

QUOTES_SELECTORS = {
    "texte": "span.text",
    "auteur": "small.author",
    "tags": ".tags meta.keywords::attr(content)",
}

QUOTES_HTML = """
<html><body>
<div class="quote" itemscope itemtype="http://schema.org/CreativeWork">
    <span class="text" itemprop="text">The world as we have created it is a process of our thinking.</span>
    <span>by <small class="author" itemprop="author">Albert Einstein</small>
    <a href="/author/Albert-Einstein">(about)</a>
    </span>
    <div class="tags">
        Tags:
        <meta class="keywords" itemprop="keywords" content="change,deep-thoughts,thinking,world" />
        <a class="tag" href="/tag/change/page/1/">change</a>
        <a class="tag" href="/tag/deep-thoughts/page/1/">deep-thoughts</a>
    </div>
</div>
<div class="quote" itemscope itemtype="http://schema.org/CreativeWork">
    <span class="text" itemprop="text">It is our choices that show what we truly are.</span>
    <span>by <small class="author" itemprop="author">J.K. Rowling</small>
    <a href="/author/J-K-Rowling">(about)</a>
    </span>
    <div class="tags">
        Tags:
        <meta class="keywords" itemprop="keywords" content="abilities,choices" />
        <a class="tag" href="/tag/abilities/page/1/">abilities</a>
    </div>
</div>
</body></html>
"""


def test_quotes_toscrape_extracts_comma_joined_tags_via_meta_content():
    # Astuce : chaque citation a un unique <meta class="keywords" content="a,b,c">
    # (contrairement aux <a class="tag"> qui sont multiples par citation et ne
    # s'aligneraient pas correctement avec le zip par position).
    pipeline = GenericPipeline(QUOTES_SELECTORS)
    items = pipeline.process(QUOTES_HTML)

    assert len(items) == 2
    assert items[0]["auteur"] == "Albert Einstein"
    assert items[0]["tags"] == "change,deep-thoughts,thinking,world"
    assert items[1]["auteur"] == "J.K. Rowling"
    assert items[1]["tags"] == "abilities,choices"


def test_quotes_toscrape_pagination_pattern():
    pagination_config = SimpleNamespace(pattern="/page/{n}/", start=1, max_pages=10)
    pipeline = PaginationPipeline(QUOTES_SELECTORS, pagination_config)

    next_url = pipeline.next_page_url(QUOTES_HTML, "https://quotes.toscrape.com/page/1/")
    assert next_url == "https://quotes.toscrape.com/page/2/"


# ---------------------------------------------------------------------------
# fr.wikipedia.org -- Niveau 2. Le sujet demande "Infobox et tableaux WikiTable".
#Les deux formats sont testes separement, avec du HTML calque sur du reel
# (verifie sur https://fr.wikipedia.org/wiki/Liste_des_presidents_de_la_Republique_francaise
# pour la wikitable, et https://fr.wikipedia.org/wiki/Emmanuel_Macron pour l'infobox).
# ---------------------------------------------------------------------------

WIKITABLE_SELECTORS = {
    "nom": "table.wikitable tr td:nth-of-type(2) a",
    "annee": "table.wikitable tr td:nth-of-type(3)",
}

WIKITABLE_HTML = """
<html><body>
<table class="wikitable">
<tbody>
<tr><th>No</th><th>Nom</th><th>Election</th></tr>
<tr><td>1</td><td><a href="/wiki/Louis-Napol%C3%A9on_Bonaparte" title="Louis-Napoleon Bonaparte">Louis-Napoleon Bonaparte</a></td><td>1848</td></tr>
<tr><td>2</td><td><a href="/wiki/Adolphe_Thiers" title="Adolphe Thiers">Adolphe Thiers</a></td><td>1871</td></tr>
</tbody>
</table>
</body></html>
"""


def test_wikipedia_wikitable_rows_are_zipped_by_position():
    pipeline = GenericPipeline(WIKITABLE_SELECTORS, base_url="https://fr.wikipedia.org")
    items = pipeline.process(WIKITABLE_HTML)

    assert len(items) == 2
    assert items[0]["nom"] == "Louis-Napoleon Bonaparte"
    assert items[0]["annee"] == "1848"
    assert items[1]["nom"] == "Adolphe Thiers"
    assert items[1]["annee"] == "1871"


# Infobox : lignes "libelle: valeur" (<th scope="row">/<td> par ligne), sauf la
# premiere ligne d'en-tete qui est un <td colspan="2"> SANS <th> associe.
WIKI_INFOBOX_SELECTORS = {
    "libelle": "table.infobox tr th[scope='row']",
    # Piege reel rencontre en testant : un simple "table.infobox tr td" desaligne
    # tout, car il inclut le <td> de la ligne d'en-tete qui n'a pas de <th>.
    # Le combinateur "+" (frere immediat) force le bon appariement par ligne.
    "valeur": "table.infobox tr th[scope='row'] + td",
}

WIKI_INFOBOX_HTML = """
<html><body>
<table class="infobox infobox--frwiki">
<tbody>
<tr><td colspan="2" class="entete">Emmanuel Macron</td></tr>
<tr><th scope="row">Election</th><td><a href="/wiki/Election_2017">7 mai 2017</a></td></tr>
<tr><th scope="row">Reelection</th><td><a href="/wiki/Election_2022">24 avril 2022</a></td></tr>
<tr><th scope="row">Predecesseur</th><td><a href="/wiki/Francois_Hollande">Francois Hollande</a></td></tr>
</tbody>
</table>
</body></html>
"""


def test_wikipedia_infobox_rows_are_correctly_paired_despite_header_row():
    pipeline = GenericPipeline(WIKI_INFOBOX_SELECTORS, base_url="https://fr.wikipedia.org")
    items = pipeline.process(WIKI_INFOBOX_HTML)

    assert len(items) == 3
    assert items[0] == {"libelle": "Election", "valeur": "7 mai 2017"}
    assert items[1] == {"libelle": "Reelection", "valeur": "24 avril 2022"}
    assert items[2] == {"libelle": "Predecesseur", "valeur": "Francois Hollande"}


def test_wikipedia_infobox_naive_td_selector_would_misalign_regression_guard():
    # Sert de garde-fou : documente pourquoi "table.infobox tr td" seul est faux
    # (decale tout d'une ligne a cause du <td> de l'en-tete sans <th>).
    naive_selectors = {
        "libelle": "table.infobox tr th[scope='row']",
        "valeur": "table.infobox tr td",
    }
    pipeline = GenericPipeline(naive_selectors, base_url="https://fr.wikipedia.org")
    items = pipeline.process(WIKI_INFOBOX_HTML)

    assert items[0] == {"libelle": "Election", "valeur": "Emmanuel Macron"}


# ---------------------------------------------------------------------------
# blogdumoderateur.com -- Niveau 3. Choisi comme le plus simple des 6 candidats
# niveau 3 restants (voir docstring du module pour la comparaison).
# ---------------------------------------------------------------------------

BLOGDUMODERATEUR_SELECTORS = {
    "titre": "h3.entry-title",
    "date": "time.entry-date::attr(datetime)",
    "categorie": "span.favtag",
}

BLOGDUMODERATEUR_HTML = """
<html><body>
<article id="post-209518" class="post-209518 post type-post status-publish format-standard hentry">
    <div class="entry-meta p-4">
        <span class="favtag">Fun</span>
        <span class="posted-on t-def ps-3">
            <time class="entry-date published updated" datetime="2026-07-31T10:32:18+02:00">31 juillet</time>
        </span>
        <header class="entry-header pt-1">
            <h3 class="entry-title h3bis">Ce qu'on a lu, vu, aime et entendu en juillet 2026 : les recos de la redaction</h3>
        </header>
    </div>
</article>
<article id="post-209500" class="post-209500 post type-post status-publish format-standard hentry">
    <div class="entry-meta p-4">
        <span class="favtag">Navigateurs</span>
        <span class="posted-on t-def ps-3">
            <time class="entry-date published updated" datetime="2026-07-31T07:00:40+02:00">31 juillet</time>
        </span>
        <header class="entry-header pt-1">
            <h3 class="entry-title h3bis">Pourquoi tous les navigateurs IA sont-ils des echecs ?</h3>
        </header>
    </div>
</article>
</body></html>
"""


def test_blogdumoderateur_extracts_titre_date_and_categorie():
    # "chapeau" (4e champ demande par le sujet) n'est pas present sur les
    # cartes de la page d'accueil (verifie sur les 44 <article> reels) --
    # meme limite structurelle que numerama pour tags/commentaires.
    # La date brute utilise ::attr(datetime) : le texte visible ("31 juillet")
    # n'a pas l'annee, l'attribut ISO est plus exploitable en aval.
    pipeline = GenericPipeline(BLOGDUMODERATEUR_SELECTORS)
    items = pipeline.process(BLOGDUMODERATEUR_HTML)

    assert len(items) == 2
    assert items[0]["categorie"] == "Fun"
    assert items[0]["date"] == "2026-07-31T10:32:18+02:00"
    assert "recos de la redaction" in items[0]["titre"]
    assert items[1]["categorie"] == "Navigateurs"
    assert "navigateurs IA" in items[1]["titre"]


# ---------------------------------------------------------------------------
# news.ycombinator.com -- Niveau 4. Choisi comme le plus simple des 3
# candidats niveau 4 restants (voir docstring du module pour la comparaison).
# ---------------------------------------------------------------------------

HN_SELECTORS = {
    "titre": "span.titleline > a",
    "url": "span.titleline > a::attr(href)",
    "domaine": "span.sitestr",
    "score": "span.score",
    # ">" (enfant direct) est indispensable ici : sans lui, "a:last-child" matche
    # aussi le lien imbrique dans <span class="age"><a>X hours ago</a></span> --
    # cet <a> est le dernier (et seul) enfant de SON parent (span.age), donc il
    # matche ":last-child" lui aussi, et etant place avant le vrai lien commentaires
    # dans le DOM, select_one() le renvoie en premier. Trouve en testant contre le
    # vrai site (le fixture precedent, sans <a> imbrique dans .age, ne l'avait pas
    # revele -- corrige aussi ci-dessous pour que ce test soit fidele au reel).
    "commentaires": ".subline > a:last-child",
}

HN_HTML = """
<html><body>
<table>
<tr class="athing submission" id="1">
  <td class="title"><span class="titleline">
    <a href="item?id=1">Ask HN: What are you working on this month?</a>
  </span></td>
</tr>
<tr><td class="subtext"><span class="subline">
  <span class="score">120 points</span> by <a class="hnuser">someone</a>
  <span class="age" title="2026-07-31T03:47:59"><a href="item?id=1">3 hours ago</a></span>
  <a href="hide?id=1">hide</a> | <a href="item?id=1">210 comments</a>
</span></td></tr>
<tr class="spacer" style="height:5px"></tr>
<tr class="athing submission" id="2">
  <td class="title"><span class="titleline">
    <a href="https://earendil.com/posts/session-portability/">The session you cannot take with you</a>
    <span class="sitebit comhead"> (<a href="from?site=earendil.com"><span class="sitestr">earendil.com</span></a>)</span>
  </span></td>
</tr>
<tr><td class="subtext"><span class="subline">
  <span class="score">369 points</span> by <a class="hnuser">apitman</a>
  <span class="age" title="2026-07-31T00:47:59"><a href="item?id=2">6 hours ago</a></span>
  <a href="hide?id=2">hide</a> | <a href="item?id=2">87 comments</a>
</span></td></tr>
</table>
</body></html>
"""


def test_hn_extracts_titre_url_score_and_comments():
    # ">" (enfant direct) est necessaire : "span.titleline a" (descendant)
    # capture aussi le lien du domaine, imbrique plus loin dans .titleline,
    # et fait apparaitre un 3e "item" fantome. Verifie en testant les deux.
    pipeline = GenericPipeline(HN_SELECTORS)
    items = pipeline.process(HN_HTML)

    assert len(items) == 2
    assert items[0]["titre"] == "Ask HN: What are you working on this month?"
    assert items[0]["score"] == "120 points"
    assert items[0]["commentaires"] == "210 comments"
    assert items[1]["titre"] == "The session you cannot take with you"
    assert items[1]["url"] == "https://earendil.com/posts/session-portability/"
    assert items[1]["score"] == "369 points"
    assert items[1]["commentaires"] == "87 comments"


def test_hn_flat_mode_misaligns_domaine_when_a_story_has_no_source_site():
    # Limite reelle du mode "flat" (par defaut, sans item_selector) : un
    # selecteur par champ, zip par position. <span class="sitestr"> n'existe
    # QUE pour les stories avec lien externe (absent des Ask HN / posts
    # internes). Ici la story 1 (Ask HN, sans domaine) recupere a tort le
    # domaine de la story 2, et la story 2 se retrouve avec un domaine vide.
    # Sert de garde-fou pour documenter pourquoi item_selector existe
    # (voir test_hn_item_selector_fixes_domaine_alignment ci-dessous).
    pipeline = GenericPipeline(HN_SELECTORS)
    items = pipeline.process(HN_HTML)

    assert items[0]["domaine"] == "earendil.com"  # faux : vole a la story 2
    assert items[1]["domaine"] == ""  # faux : devrait etre "earendil.com"


def test_hn_item_selector_fixes_domaine_alignment():
    # Avec item_selector="tr.athing", chaque champ est cherche a l'interieur
    # de SON PROPRE conteneur -- avec repli sur le <tr> suivant immediat,
    # necessaire ici car score/commentaires sont dans la ligne "subtext" qui
    # suit le <tr class="athing">, pas dedans. Le domaine absent d'une story
    # ne contamine plus les autres.
    pipeline = GenericPipeline(HN_SELECTORS, item_selector="tr.athing")
    items = pipeline.process(HN_HTML)

    assert len(items) == 2
    assert items[0]["titre"] == "Ask HN: What are you working on this month?"
    assert items[0]["domaine"] == ""  # correct cette fois : pas de lien externe
    assert items[0]["score"] == "120 points"  # toujours trouve via le repli sur le tr suivant
    assert items[0]["commentaires"] == "210 comments"
    assert items[1]["titre"] == "The session you cannot take with you"
    assert items[1]["domaine"] == "earendil.com"  # correct : plus vole a personne
    assert items[1]["score"] == "369 points"


def test_hn_pagination_pattern():
    pagination_config = SimpleNamespace(pattern="?p={n}", start=1, max_pages=5)
    pipeline = PaginationPipeline(HN_SELECTORS, pagination_config)

    next_url = pipeline.next_page_url(HN_HTML, "https://news.ycombinator.com/")
    assert next_url == "https://news.ycombinator.com/?p=2"
