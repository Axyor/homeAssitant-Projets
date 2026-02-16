import urllib.request
import urllib.parse
import urllib.error
import json
import datetime
import sys
import os
import logging
from logging.handlers import RotatingFileHandler

# CONFIGURATION
# Chemin absolu par défaut, basé sur l'emplacement du script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEYWORDS_FILE = os.path.join(SCRIPT_DIR, "mots_cles.txt")
CACHE_FILE = os.path.join(SCRIPT_DIR, "rappels_vus.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "rappel.log")

# API V2 Rappel Conso
BASE_URL = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/rappelconso-v2-gtin-trie/records"
DAYS_BACK = 14  # Nombre de jours en arrière
LIMIT = 50      # Nombre max de résultats par requête

# --- Logging ---
logger = logging.getLogger("rappelconso")

def setup_logging(verbose=False):
    """Configure le logging dans un fichier et optionnellement en console."""
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    
    # Fichier log avec rotation : max 100 Ko, pas de backup (l'ancien est supprimé)
    try:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=100_000, backupCount=0, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(fh)
    except Exception:
        pass  # Si impossible d'écrire le log, on continue silencieusement
    
    if verbose:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(ch)


# --- Cache des rappels déjà vus ---
def load_cache():
    """Charge le cache des rappels déjà notifiés."""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        logger.warning("Cache corrompu, réinitialisation.")
        return {}

def save_cache(cache):
    """Sauvegarde le cache des rappels vus."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"Impossible de sauvegarder le cache: {e}")

def update_cache(cache, results):
    """Met à jour le cache avec les nouveaux rappels. Retourne la liste des nouveaux.
    
    Nettoie aussi les entrées du cache plus vieilles que DAYS_BACK * 2 jours.
    """
    cutoff = (datetime.date.today() - datetime.timedelta(days=DAYS_BACK * 2)).isoformat()
    
    # Nettoyage des anciennes entrées
    old_keys = [k for k, v in cache.items() if v.get("first_seen", "") < cutoff]
    for k in old_keys:
        del cache[k]
        logger.debug(f"Cache nettoyé: {k}")
    
    nouveaux = []
    for r in results:
        fiche_id = r.get("numero_fiche", "")
        if fiche_id and fiche_id not in cache:
            cache[fiche_id] = {
                "first_seen": datetime.date.today().isoformat(),
                "titre": r.get("titre", "")
            }
            nouveaux.append(r)
            logger.info(f"Nouveau rappel: [{fiche_id}] {r.get('titre', '?')}")
    
    return nouveaux


# --- Lecture des mots-clés ---
def get_keywords(filepath):
    """Lit les mots clés depuis le fichier texte."""
    if not os.path.exists(filepath):
        logger.error(f"Fichier de mots-clés introuvable: {filepath}")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        keywords = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    logger.info(f"Mots-clés chargés: {keywords}")
    return keywords


# --- Construction de la requête ---
def build_query(keywords, days_back):
    """Construit la clause 'where' pour l'API V2.
    
    Recherche multi-champs : libellé + sous-catégorie + marque du produit.
    """
    if not keywords:
        return None
    
    # 1. Filtre sur la date
    cutoff_date = (datetime.date.today() - datetime.timedelta(days=days_back)).isoformat()
    date_clause = f"date_publication >= date'{cutoff_date}'"
    
    # 2. Recherche multi-champs pour chaque mot-clé
    keyword_clauses = []
    for kw in keywords:
        clause = (
            f"(search(libelle, \"{kw}\") OR "
            f"search(sous_categorie_produit, \"{kw}\") OR "
            f"search(marque_produit, \"{kw}\") OR "
            f"search(distributeurs, \"{kw}\"))"
        )
        keyword_clauses.append(clause)
    
    or_block = " OR ".join(keyword_clauses)
    
    # Combinaison : (Date récente) ET (Mot clé 1 OU Mot clé 2...)
    full_where = f"{date_clause} AND ({or_block})"
    logger.debug(f"Requête construite: {full_where}")
    return full_where


# --- Appel API ---
def fetch_rappels():
    """Récupère les rappels depuis l'API et les traite."""
    keywords = get_keywords(KEYWORDS_FILE)
    if not keywords:
        return {"error": "Aucun mot clé défini", "count": 0, "new_count": 0, "data": [], "nouveaux": []}

    where_clause = build_query(keywords, DAYS_BACK)
    
    params = {
        "order_by": "date_publication DESC",
        "limit": LIMIT,
        "where": where_clause
    }
    
    query_string = urllib.parse.urlencode(params)
    url = f"{BASE_URL}?{query_string}"
    logger.debug(f"Appel API: {url}")
    
    req = urllib.request.Request(url, headers={
        "User-Agent": "HomeAssistant-RappelConso-Integration/2.0"
    })
    
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw_data = json.loads(response.read().decode())
            results = raw_data.get("results", [])
            logger.info(f"API OK: {raw_data.get('total_count', 0)} résultats trouvés")
            
            # Structure simplifiée pour HA (champs API V2)
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
            
            # Gestion du cache — identifier les nouveaux rappels
            cache = load_cache()
            nouveaux = update_cache(cache, data)
            save_cache(cache)
            
            if nouveaux:
                logger.info(f"{len(nouveaux)} nouveau(x) rappel(s) détecté(s)")
            
            output = {
                "count": raw_data.get("total_count", 0),
                "new_count": len(nouveaux),
                "last_update": datetime.datetime.now().isoformat(),
                "keywords_used": keywords,
                "data": data,
                "nouveaux": [
                    {"titre": r.get("titre"), "marque": r.get("marque"), "numero_fiche": r.get("numero_fiche")}
                    for r in nouveaux
                ],
            }
            return output
            
    except urllib.error.HTTPError as e:
        msg = f"HTTP {e.code}: {e.reason}"
        logger.error(f"Erreur API: {msg}")
        return {"error": msg, "count": 0, "new_count": 0, "data": [], "nouveaux": []}
    except urllib.error.URLError as e:
        msg = f"Connexion impossible: {e.reason}"
        logger.error(f"Erreur réseau: {msg}")
        return {"error": msg, "count": 0, "new_count": 0, "data": [], "nouveaux": []}
    except json.JSONDecodeError:
        msg = "Réponse API invalide (pas du JSON)"
        logger.error(msg)
        return {"error": msg, "count": 0, "new_count": 0, "data": [], "nouveaux": []}
    except Exception as e:
        msg = f"Erreur inattendue: {str(e)}"
        logger.error(msg)
        return {"error": msg, "count": 0, "new_count": 0, "data": [], "nouveaux": []}


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv
    setup_logging(verbose=verbose)
    
    # Chemin du fichier de mots-clés en argument (optionnel)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        KEYWORDS_FILE = args[0]
        
    result = fetch_rappels()
    print(json.dumps(result, indent=2, ensure_ascii=False))
