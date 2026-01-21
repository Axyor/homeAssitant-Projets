import urllib.request
import urllib.parse
import json
import datetime
import sys
import os

# CONFIGURATION
# Chemin vers le fichier de mots clés (relatif ou absolu)
KEYWORDS_FILE = "mots_cles.txt"
BASE_URL = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/rappelconso0/records"
DAYS_BACK = 14  # Nombre de jours en arrière

def get_keywords(filepath):
    """Lit les mots clés depuis le fichier texte."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        # Nettoie les lignes vides et les espaces
        return [line.strip() for line in f if line.strip()]

def build_query(keywords, days_back):
    """Construit la clause 'where' pour l'API."""
    if not keywords:
        return None
    
    # 1. Gestion de la date
    cutoff_date = (datetime.date.today() - datetime.timedelta(days=days_back)).isoformat()
    date_clause = f"date_de_publication >= date'{cutoff_date}'"
    
    # 2. Gestion des mots clés (Logique OR)
    # search(libelle, "mot") est plus large qu'un simple égal
    keyword_clauses = [f'search(libelle, "{kw}")' for kw in keywords]
    or_block = " OR ".join(keyword_clauses)
    
    # Combinaison : (Date récente) ET (Mot clé 1 OU Mot clé 2...)
    full_where = f"{date_clause} AND ({or_block})"
    return full_where

def fetch_rappels():
    keywords = get_keywords(KEYWORDS_FILE)
    if not keywords:
        return {"error": "Aucun mot clé défini", "count": 0, "data": []}

    where_clause = build_query(keywords, DAYS_BACK)
    
    params = {
        "order_by": "date_de_publication DESC",
        "limit": 10, # Limite pour ne pas surcharger le sensor HA
        "where": where_clause
    }
    
    query_string = urllib.parse.urlencode(params)
    url = f"{BASE_URL}?{query_string}"
    
    # Utilisation d'un User-Agent personnalisé pour être "poli" envers l'API
    req = urllib.request.Request(url, headers={
        "User-Agent": "HomeAssistant-RappelConso-Integration/1.0"
    })
    
    try:
        with urllib.request.urlopen(req) as response:
            raw_data = json.loads(response.read().decode())
            results = raw_data.get("results", [])
            
            # On retourne une structure simplifiée pour HA
            output = {
                "count": raw_data.get("total_count", 0),
                "last_update": datetime.datetime.now().isoformat(),
                "keywords_used": keywords,
                "data": [
                    {
                        "titre": r.get("libelle"),
                        "marque": r.get("nom_de_la_marque_du_produit"),
                        "motif": r.get("motif_du_rappel"),
                        "date": r.get("date_de_publication"),
                        "url": r.get("lien_vers_la_fiche_rappel"),
                        "image_url": r.get("liens_vers_les_images", "").split("|")[0] if r.get("liens_vers_les_images") else None
                    }
                    for r in results
                ]
            }
            return output
            
    except Exception as e:
        return {"error": str(e), "count": 0, "data": []}

if __name__ == "__main__":
    # Pour tester en local, on s'assure d'être dans le bon dossier ou on passe le chemin
    if len(sys.argv) > 1:
        KEYWORDS_FILE = sys.argv[1]
        
    result = fetch_rappels()
    print(json.dumps(result, indent=2, ensure_ascii=False))
