import urllib.request
import urllib.parse
import urllib.error
import json
import datetime
import sys
import os
import logging
from logging.handlers import RotatingFileHandler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEYWORDS_FILE = os.path.join(SCRIPT_DIR, "mots_cles.txt")
CACHE_FILE = os.path.join(SCRIPT_DIR, "rappels_vus.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "rappel.log")

BASE_URL = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/rappelconso-v2-gtin-trie/records"
DAYS_BACK = 30
LIMIT = 100

logger = logging.getLogger("rappelconso")

def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    try:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=100_000, backupCount=0, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(fh)
    except Exception:
        pass

    if verbose:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(ch)


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        logger.warning("Corrupted cache, resetting.")
        return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"Unable to save cache: {e}")

def update_cache(cache, results):
    cutoff = (datetime.date.today() - datetime.timedelta(days=DAYS_BACK * 2)).isoformat()

    old_keys = [k for k, v in cache.items() if v.get("first_seen", "") < cutoff]
    for k in old_keys:
        del cache[k]
        logger.debug(f"Cache cleaned: {k}")

    new_items = []
    for r in results:
        record_id = r.get("numero_fiche", "")
        if record_id and record_id not in cache:
            cache[record_id] = {
                "first_seen": datetime.date.today().isoformat(),
                "titre": r.get("titre", "")
            }
            new_items.append(r)
            logger.info(f"New recall: [{record_id}] {r.get('titre', '?')}")

    return new_items


def get_config(filepath):
    """Parse le fichier mots-clés avec sections [distributeurs], [produits], [surveillance].

    Format:
        [distributeurs]    -> magasins fréquentés (filtrage AND avec produits)
        [surveillance]     -> produits critiques, jamais filtrés par distributeur
        [produits]         -> produits courants, filtrés par distributeurs

    Rétro-compatible : sans sections, tout va dans 'produits' (pas de filtrage distributeur).
    """
    config = {"distributeurs": [], "produits": [], "surveillance": []}

    if not os.path.exists(filepath):
        logger.error(f"Keywords file not found: {filepath}")
        return config

    current_section = "produits"  # section par défaut (rétro-compatibilité)

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Détection de section
            if stripped.startswith("[") and stripped.endswith("]"):
                section_name = stripped[1:-1].strip().lower()
                if section_name in config:
                    current_section = section_name
                else:
                    logger.warning(f"Unknown section: {stripped}")
                continue
            config[current_section].append(stripped)

    logger.info(f"Config loaded — distributeurs: {config['distributeurs']}, "
                f"produits: {config['produits']}, surveillance: {config['surveillance']}")
    return config


def _search_clause(keyword):
    """Construit une clause de recherche multi-champs pour un mot-clé."""
    return (
        f"(search(libelle, \"{keyword}\") OR "
        f"search(sous_categorie_produit, \"{keyword}\") OR "
        f"search(marque_produit, \"{keyword}\") OR "
        f"search(distributeurs, \"{keyword}\"))"
    )


def build_query(config, days_back):
    produits = config.get("produits", [])
    distributeurs = config.get("distributeurs", [])
    surveillance = config.get("surveillance", [])

    if not produits and not surveillance:
        return None

    cutoff_date = (datetime.date.today() - datetime.timedelta(days=days_back)).isoformat()
    date_clause = f"date_publication >= date'{cutoff_date}'"

    blocks = []

    # Bloc produits × distributeurs (filtrage croisé)
    if produits:
        produit_clauses = [_search_clause(kw) for kw in produits]
        produit_block = " OR ".join(produit_clauses)

        if distributeurs:
            distrib_clauses = [f"search(distributeurs, \"{d}\")" for d in distributeurs]
            distrib_block = " OR ".join(distrib_clauses)
            blocks.append(f"(({produit_block}) AND ({distrib_block}))")
        else:
            blocks.append(f"({produit_block})")

    # Bloc surveillance (jamais filtré par distributeur)
    if surveillance:
        surv_clauses = [_search_clause(kw) for kw in surveillance]
        surv_block = " OR ".join(surv_clauses)
        blocks.append(f"({surv_block})")

    combined = " OR ".join(blocks)
    full_where = f"{date_clause} AND ({combined})"
    logger.debug(f"Query built: {full_where}")
    return full_where


def fetch_recalls():
    config = get_config(KEYWORDS_FILE)
    all_keywords = config["produits"] + config["surveillance"]
    if not all_keywords:
        return {"error": "No keywords defined", "count": 0, "new_count": 0, "data": [], "nouveaux": []}

    where_clause = build_query(config, DAYS_BACK)

    params = {
        "order_by": "date_publication DESC",
        "limit": LIMIT,
        "where": where_clause
    }

    query_string = urllib.parse.urlencode(params)
    url = f"{BASE_URL}?{query_string}"
    logger.debug(f"API call: {url}")

    req = urllib.request.Request(url, headers={
        "User-Agent": "HomeAssistant-RappelConso-Integration/2.0"
    })

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw_data = json.loads(response.read().decode())
            results = raw_data.get("results", [])
            logger.info(f"API OK: {raw_data.get('total_count', 0)} results found")

            data = [
                {
                    "titre": r.get("libelle"),
                    "marque": r.get("marque_produit"),
                    "motif": r.get("motif_rappel"),
                    "date": r.get("date_publication"),
                    "url": r.get("lien_vers_la_fiche_rappel"),
                    "image_url": r.get("liens_vers_les_images", "").split("|")[0] if r.get("liens_vers_les_images") else None,
                    "risques": r.get("risques_encourus"),
                    "description_risque": r.get("description_complementaire_risque"),
                    "categorie": r.get("categorie_produit"),
                    "sous_categorie": r.get("sous_categorie_produit"),
                    "distributeurs": r.get("distributeurs"),
                    "conduite": r.get("conduites_a_tenir_par_le_consommateur"),
                    "numero_fiche": r.get("numero_fiche"),
                    "preconisations": (r.get("preconisations_sanitaires") or "")[:200] or None,
                }
                for r in results
            ]

            seen_records = set()
            unique_data = []
            for d in data:
                record = d.get("numero_fiche", "")
                if record and record not in seen_records:
                    seen_records.add(record)
                    unique_data.append(d)
            data = unique_data
            logger.info(f"{len(results)} API results -> {len(data)} unique records after deduplication")

            cache = load_cache()
            new_items = update_cache(cache, data)
            save_cache(cache)

            if new_items:
                logger.info(f"{len(new_items)} new recall(s) detected")

            output = {
                "count": len(data),
                "new_count": len(new_items),
                "last_update": datetime.datetime.now().isoformat(),
                "keywords_used": config["produits"],
                "distributeurs_used": config["distributeurs"],
                "surveillance_used": config["surveillance"],
                "data": data,
                "nouveaux": [
                    {"titre": r.get("titre"), "marque": r.get("marque"), "numero_fiche": r.get("numero_fiche")}
                    for r in new_items
                ],
            }
            return output

    except urllib.error.HTTPError as e:
        msg = f"HTTP {e.code}: {e.reason}"
        logger.error(f"API error: {msg}")
        return {"error": msg, "count": 0, "new_count": 0, "data": [], "nouveaux": []}
    except urllib.error.URLError as e:
        msg = f"Connection failed: {e.reason}"
        logger.error(f"Network error: {msg}")
        return {"error": msg, "count": 0, "new_count": 0, "data": [], "nouveaux": []}
    except json.JSONDecodeError:
        msg = "Invalid API response (not JSON)"
        logger.error(msg)
        return {"error": msg, "count": 0, "new_count": 0, "data": [], "nouveaux": []}
    except Exception as e:
        msg = f"Unexpected error: {str(e)}"
        logger.error(msg)
        return {"error": msg, "count": 0, "new_count": 0, "data": [], "nouveaux": []}


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv
    setup_logging(verbose=verbose)

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        KEYWORDS_FILE = args[0]

    result = fetch_recalls()
    print(json.dumps(result, indent=2, ensure_ascii=False))
