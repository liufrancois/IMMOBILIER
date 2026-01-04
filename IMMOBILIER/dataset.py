
import re
import csv
import time
import sys
from urllib.parse import urljoin
from typing import Optional, Set, List

import requests
from bs4 import BeautifulSoup


_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
})


class NonValide(Exception):
    """
    Exception levée lorsqu'une annonce ne respecte pas les critères de sélection.
    """
    pass

def _clean(s: str) -> str:
    s = s.replace("\xa0", " ")
    s = " ".join(s.split())
    return s.strip()


def _is_visible_text_node(node) -> bool:
    """
    True si node est un texte "visible" (pas dans <script>/<style>/<noscript>).
    """
    parent = getattr(node, "parent", None)
    if parent is None:
        return False
    return parent.name not in {"script", "style", "noscript"}


def getsoup(url: str, timeout: int = 15, retries: int = 2, sleep_retry: float = 0.8) -> BeautifulSoup:
    """
    Télécharge une page HTML et renvoie la soupe correspondante.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL vide ou invalide.")

    last_exc = None
    for _ in range(retries + 1):
        try:
            r = _SESSION.get(url, timeout=timeout)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            last_exc = e
            time.sleep(sleep_retry)

    raise last_exc


def prix(soup: BeautifulSoup) -> str:
    """
    Renvoie le prix (string) sans le symbole €.
    Lève NonValide si prix < 10 000 ou si introuvable/illisible.
    """
    marker = soup.find(string=re.compile(r"\bà vendre\b", re.IGNORECASE))
    euro_pattern = re.compile(r"€\s*[\d\s\u00A0]+|[\d\s\u00A0]+€")

    #On évite de matcher dans les scripts
    def find_price_text():
        if marker:
            for node in marker.find_all_next(string=euro_pattern):
                if _is_visible_text_node(node):
                    return node
        for node in soup.find_all(string=euro_pattern):
            if _is_visible_text_node(node):
                return node
        return None

    price_text = find_price_text()
    if not price_text:
        raise NonValide("Prix introuvable sur la page.")

    raw = str(price_text).strip()
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        raise NonValide(f"Prix illisible: {raw!r}")

    if int(digits) < 10_000:
        raise NonValide(f"Annonce rejetée : prix < 10 000 ({digits})")

    return digits


def ville(soup: BeautifulSoup) -> str:
    """
    Renvoie la ville où se trouve le bien.
    La ville est la sous-chaîne après la dernière occurrence de ', '.
    (On ignore les contenus dans <script>/<style> pour éviter le JSON-LD.)
    """
    loc_pattern = re.compile(r"France,\s", re.IGNORECASE)
    marker = soup.find(string=re.compile(r"\bà vendre\b", re.IGNORECASE))

    candidates: List[str] = []

    search_iter = marker.find_all_next(string=loc_pattern) if marker else soup.find_all(string=loc_pattern)

    for node in search_iter:
        if not _is_visible_text_node(node):
            continue

        txt = _clean(str(node))

        #Filtre anti-JSON/URL
        if "http" in txt or '"url"' in txt or "{" in txt or "}" in txt:
            continue

        if txt.count(",") < 3:
            continue

        candidates.append(txt)
        if len(candidates) >= 10:
            break

    if not candidates:
        raise NonValide("Localisation introuvable (donc ville introuvable).")

    loc = min(candidates, key=len)

    idx = loc.rfind(", ")
    if idx == -1 or idx + 2 >= len(loc):
        raise NonValide(f"Format de localisation inattendu: {loc!r}")

    return loc[idx + 2:].strip()

def caracteristiques(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Renvoie la balise contenant le bloc de caractéristiques.
    On cherche un header proche de “Caractéristiques” ou “Détails De La Propriété”.
    """
    title_patterns = [
        r"Détails\s+De\s+La\s+Propriété",
        r"Caractéristiques",
    ]

    for pat in title_patterns:
        node = soup.find(string=re.compile(pat, re.IGNORECASE))
        if not node:
            continue

        tag = node.parent
        for _ in range(7):
            if tag is None:
                break
            blob = _clean(tag.get_text(" ", strip=True)).lower()
            score = sum(k in blob for k in [
                "type", "surface", "nb. de pièces", "nb. de chambres", "nb. de salles de bains", "dep", "dpe"
            ])
            if score >= 3:
                return tag
            tag = tag.parent

    return soup


def _extract_value(root: BeautifulSoup, label_regex: str) -> str:
    """
    Extrait la valeur associée à un libellé (Type, Surface, etc.).
    """
    label_node = root.find(string=re.compile(label_regex, re.IGNORECASE))
    if not label_node:
        raise NonValide(f"Champ introuvable: {label_regex}")

    label_tag = label_node.parent

    tr = label_tag.find_parent("tr")
    if tr:
        cells = tr.find_all(["td", "th"])
        texts = [_clean(c.get_text(" ", strip=True)) for c in cells]
        for i, t in enumerate(texts):
            if re.fullmatch(label_regex, t, flags=re.IGNORECASE):
                if i + 1 < len(texts):
                    return texts[i + 1]
        for t in reversed(texts):
            if t:
                return t

    parent = label_tag.parent
    if parent:
        children = [c for c in parent.children if getattr(c, "get_text", None)]
        for i, c in enumerate(children):
            if c is label_tag:
                for j in range(i + 1, len(children)):
                    cand = _clean(children[j].get_text(" ", strip=True))
                    if cand and not re.fullmatch(label_regex, cand, flags=re.IGNORECASE):
                        return cand

    nxt = label_tag.find_next(string=True)
    while nxt is not None:
        if _is_visible_text_node(nxt):
            txt = _clean(str(nxt))
            if txt and not re.fullmatch(label_regex, txt, flags=re.IGNORECASE):
                return txt
        nxt = nxt.find_next(string=True) if hasattr(nxt, "find_next") else None

    raise NonValide(f"Valeur introuvable pour: {label_regex}")


def _digits_or_dash(value: str) -> str:
    v = _clean(value)
    if v in {"-", ""}:
        return "-"
    d = re.sub(r"[^\d]", "", v)
    return d if d else "-"


def type(soup: BeautifulSoup) -> str:
    """
    Renvoie le type du bien.
    Lève NonValide si le type n'est ni 'Maison' ni 'Appartement'.
    """
    root = caracteristiques(soup)
    t = _clean(_extract_value(root, r"Type"))
    if t not in {"Maison", "Appartement"}:
        raise NonValide(f"Type non autorisé: {t}")
    return t


def surface(soup: BeautifulSoup) -> str:
    root = caracteristiques(soup)
    try:
        raw = _extract_value(root, r"Surface")
        return _digits_or_dash(raw)
    except NonValide:
        return "-"


def nbrpieces(soup: BeautifulSoup) -> str:
    root = caracteristiques(soup)
    try:
        raw = _extract_value(root, r"Nb\.\s*de\s*pièces|Nombre\s+de\s*pièces")
        return _digits_or_dash(raw)
    except NonValide:
        return "-"


def nbrchambres(soup: BeautifulSoup) -> str:
    root = caracteristiques(soup)
    try:
        raw = _extract_value(root, r"Nb\.\s*de\s*chambres|Nombre\s+de\s*chambres")
        return _digits_or_dash(raw)
    except NonValide:
        return "-"


def nbrsdb(soup: BeautifulSoup) -> str:
    root = caracteristiques(soup)
    try:
        raw = _extract_value(root, r"Nb\.\s*de\s*salles?\s*de\s*bains?")
        return _digits_or_dash(raw)
    except NonValide:
        return "-"


def dpe(soup: BeautifulSoup) -> str:
    root = caracteristiques(soup)
    try:
        raw = _clean(_extract_value(root, r"DEP|DPE|Consommation\s+d'?énergie"))
    except NonValide:
        return "-"

    if raw in {"-", ""}:
        return "-"

    m = re.search(r"\b([A-G])\b", raw, flags=re.IGNORECASE)
    return m.group(1).upper() if m else raw


def informations_fields(soup: BeautifulSoup) -> List[str]:
    return [
        ville(soup),
        type(soup),
        surface(soup),
        nbrpieces(soup),
        nbrchambres(soup),
        nbrsdb(soup),
        dpe(soup),
        prix(soup),
    ]


def informations(soup: BeautifulSoup) -> str:
    return ",".join(informations_fields(soup))



_AD_URL_RE = re.compile(r"/annonce-[^/]+/\d+", re.IGNORECASE)

#URLs de départ
START_URLS_IDF = [
    "https://ile-de-france.immo-entre-particuliers.com/annonces/france-ile-de-france/vente/maison/",
    "https://ile-de-france.immo-entre-particuliers.com/annonces/france-ile-de-france/vente/appartement/",
]


def extract_ad_urls(listing_soup: BeautifulSoup, page_url: str) -> Set[str]:
    """
    Extrait les URLs d'annonces depuis une page de résultats.
    """
    urls: Set[str] = set()
    for a in listing_soup.find_all("a", href=True):
        href = a["href"]
        if _AD_URL_RE.search(href):
            urls.add(urljoin(page_url, href))
    return urls


def find_next_page_url(listing_soup: BeautifulSoup, page_url: str) -> Optional[str]:
    """
    Trouve l'URL de la page suivante.
    """
    link_next = listing_soup.find("a", attrs={"rel": re.compile(r"\bnext\b", re.IGNORECASE)}, href=True)
    if link_next and link_next.get("href"):
        return urljoin(page_url, link_next["href"])

    for a in listing_soup.find_all("a", href=True):
        txt = a.get_text(" ", strip=True).lower()
        if "suivant" in txt:
            return urljoin(page_url, a["href"])

    for a in listing_soup.find_all("a", href=True):
        attrs = " ".join(a.get("class", [])).lower() + " " + str(a.get("id", "")).lower()
        if "next" in attrs:
            return urljoin(page_url, a["href"])

    return None


def scrape_idf_sales_to_csv(
    output_csv: str = "data/raw/idf_ventes.csv",
    delay_listing_s: float = 0.4,
    delay_ad_s: float = 0.4,
    max_pages_safety: int = 400,
    print_every: int = 25,          # point d'étape toutes les N annonces
    print_each_valid: bool = False, # True = affiche chaque annonce valide (très verbeux)
) -> None:
    """
    Parcourt toutes les pages de résultats IDF (ventes maison + ventes appartement),
    appelle informations_fields() sur chaque annonce, et écrit dans le CSV.
    """
    header = ["Ville", "Type", "Surface", "NbrPieces", "NbrChambres", "NbrSdb", "DPE", "Prix"]

    seen_ads: Set[str] = set()
    total_ads = 0
    valid_ads = 0
    skipped_ads = 0

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        f.flush()

        print(f"[START] CSV créé: {output_csv}", flush=True)

        for start_url in START_URLS_IDF:
            page_url = start_url
            pages_seen = 0

            print(f"\n[SECTION] Début: {start_url}", flush=True)

            while page_url:
                pages_seen += 1
                if pages_seen > max_pages_safety:
                    print("[WARN] max_pages_safety atteint, arrêt de cette section.", flush=True)
                    break

                print(f"\n[PAGE {pages_seen}] {page_url}", flush=True)

                listing_soup = getsoup(page_url)
                ad_urls = extract_ad_urls(listing_soup, page_url)
                print(f"[PAGE {pages_seen}] Annonces trouvées sur la page: {len(ad_urls)}", flush=True)

                for ad_url in sorted(ad_urls):
                    if ad_url in seen_ads:
                        continue
                    seen_ads.add(ad_url)
                    total_ads += 1

                    try:
                        ad_soup = getsoup(ad_url)
                        row = informations_fields(ad_soup)
                        writer.writerow(row)
                        valid_ads += 1

                        if print_each_valid:
                            print(f"[OK] {','.join(row)} | {ad_url}", flush=True)

                    except NonValide:
                        skipped_ads += 1
                    except Exception:
                        skipped_ads += 1

                    if total_ads % print_every == 0:
                        print(f"[PROGRESS] total={total_ads} | valides={valid_ads} | ignorées={skipped_ads}", flush=True)
                        f.flush()

                    time.sleep(delay_ad_s)

                page_url = find_next_page_url(listing_soup, page_url)
                time.sleep(delay_listing_s)

        f.flush()

    print(f"\n[END] Visitées={total_ads} | Valides={valid_ads} | Ignorées={skipped_ads} | CSV={output_csv}", flush=True)


if __name__ == "__main__":

    if len(sys.argv) >= 2 and sys.argv[1] == "--idf":
        out = sys.argv[2] if len(sys.argv) >= 3 else "data/raw/idf_ventes.csv"
        scrape_idf_sales_to_csv(output_csv=out)
        sys.exit(0)

    #Test simple sur une annonce
    test_url = "https://www.immo-entre-particuliers.com/annonce-gironde-bordeaux/411049-grande-echoppe-de-charme-a-renover-avec-250m2-jardin-plein-sud-et-dependance-bordeaux-camille-godard"
    soup = getsoup(test_url)

    print("TITLE:", soup.title.text.strip() if soup.title else "Aucun title trouvé")

    try:
        print("PRIX (sans €):", prix(soup))
        print("VILLE:", ville(soup))
        print("TYPE:", type(soup))
        print("SURFACE:", surface(soup))
        print("NB PIECES:", nbrpieces(soup))
        print("NB CHAMBRES:", nbrchambres(soup))
        print("NB SDB:", nbrsdb(soup))
        print("DPE:", dpe(soup))
        print("INFOS:", informations(soup))
    except NonValide as e:
        print("NonValide:", e)