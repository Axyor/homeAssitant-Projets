import urllib.request
import urllib.error
import urllib.parse
import json
import datetime
import argparse

BASE_URL = "https://hubeau.eaufrance.fr/api/v1/qualite_eau_potable/resultats_dis"

def fetch_water_quality(commune_code):
    try:
        # Request 1: Get ONLY the latest sample code
        params_latest = urllib.parse.urlencode({
            "code_commune": commune_code,
            "size": 1,
            "sort": "desc",
            "order_by": "date_prelevement"
        })
        url_latest = f"{BASE_URL}?{params_latest}"
        req_latest = urllib.request.Request(url_latest, headers={"User-Agent": "HomeAssistant-EauQualite-Integration/1.1"})
        
        with urllib.request.urlopen(req_latest, timeout=20) as response_latest:
            raw_data_latest = json.loads(response_latest.read().decode())
            results_latest = raw_data_latest.get("data", [])
            
            if not results_latest:
                return {
                    "compliant": False, 
                    "error": "No data found for this municipality.",
                    "conclusion": "No data",
                    "commune_name": "Unknown",
                    "hardness": "N/A",
                    "nitrates": "N/A",
                    "ph": "N/A",
                    "parameters": []
                }
            
            latest_code = results_latest[0].get("code_prelevement")
            if latest_code is None:
                return {
                    "compliant": False, 
                    "error": "Missing sample code in data.",
                    "conclusion": "Error",
                    "commune_name": "Unknown",
                    "hardness": "N/A",
                    "nitrates": "N/A",
                    "ph": "N/A",
                    "parameters": []
                }
                
        # Request 2: Fetch ALL parameters for this precise sample
        # We set size=100 just in case there are many parameters for one sample
        params_all = urllib.parse.urlencode({
            "code_commune": commune_code,
            "code_prelevement": latest_code,
            "size": 100 
        })
        url_all = f"{BASE_URL}?{params_all}"
        req_all = urllib.request.Request(url_all, headers={"User-Agent": "HomeAssistant-EauQualite-Integration/1.1"})
        
        with urllib.request.urlopen(req_all, timeout=20) as response_all:
            raw_data_all = json.loads(response_all.read().decode())
            latest_tests = raw_data_all.get("data", [])
            
            if not latest_tests:
                return {
                    "compliant": False, 
                    "error": "Analysis parameters problem.",
                    "conclusion": "Error",
                    "commune_name": "Unknown",
                    "hardness": "N/A",
                    "nitrates": "N/A",
                    "ph": "N/A",
                    "parameters": []
                }
                
            info = latest_tests[0]
            
            latest_date = info.get("date_prelevement")
            latest_date = str(latest_date) if latest_date is not None else "Unknown date"
            
            commune_name = info.get("nom_commune")
            commune_name = str(commune_name) if commune_name is not None else "Unknown"
            conclusion = info.get("conclusion_conformite_prelevement")
            conclusion = str(conclusion) if conclusion is not None else "No conclusion transmitted."
            
            # Extract detailed parameters
            parameters = []
            hardness = "N/A"
            nitrates = "N/A"
            ph = "N/A"
            
            for test in latest_tests:
                name = test.get("libelle_parametre")
                name = str(name) if name is not None else "Unknown"
                
                val_alpha = test.get("resultat_alphanumerique")
                val_num = test.get("resultat_numerique")
                val_raw = val_alpha if val_alpha is not None else val_num
                val = str(val_raw).strip() if val_raw is not None else "N/A"
                
                unit_raw = test.get("libelle_unite")
                unit = str(unit_raw).strip() if unit_raw is not None else ""
                
                ref_qual = test.get("reference_qualite_parametre")
                lim_qual = test.get("limite_qualite_parametre")
                ref = str(ref_qual).strip() if ref_qual is not None else (str(lim_qual).strip() if lim_qual is not None else "N/A")
                
                parameters.append({
                    "name": name,
                    "value": val,
                    "unit": unit,
                    "reference": ref
                })
                
                name_lower = name.lower()
                metric_str = f"{val} {unit}".strip() if val != "N/A" else "N/A"
                if "titre hydrotimétrique" in name_lower:
                    hardness = metric_str
                elif "nitrates" in name_lower:
                    nitrates = metric_str
                elif "potentiel en hydrogène" in name_lower or name_lower == "ph":
                    ph = metric_str
            
            # Sort parameters alphabetically for better display
            parameters.sort(key=lambda x: x["name"])
            
            # Simple heuristic: if the conclusion contains "non conforme", it's not good.
            is_compliant = "non conforme" not in conclusion.lower()
            
            network = info.get("nom_uge")
            if not network:
                network = info.get("nom_distributeur")
            network = str(network) if network is not None else "Unknown"
            
            bact = info.get("conformite_limites_bact_prelevement")
            bact = str(bact) if bact is not None else "N/A"
            
            pc = info.get("conformite_limites_pc_prelevement")
            pc = str(pc) if pc is not None else "N/A"
            
            return {
                "compliant": is_compliant,
                "sampling_date": latest_date,
                "commune_name": commune_name,
                "conclusion": conclusion,
                "network": network,
                "bact_compliance": bact,
                "pc_compliance": pc,
                "hardness": hardness,
                "nitrates": nitrates,
                "ph": ph,
                "parameters": parameters,
                "last_update": datetime.datetime.now().isoformat()
            }
            
    except Exception as e:
         return {
             "compliant": False,
             "conclusion": "Error",
             "error": str(e),
             "commune_name": "Unknown",
             "hardness": "N/A",
             "nitrates": "N/A",
             "ph": "N/A",
             "parameters": []
         }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieves drinking water quality via Hub'Eau.")
    parser.add_argument("--commune", required=True, help="INSEE code of the municipality (e.g., 59328)")
    args = parser.parse_args()
    
    result = fetch_water_quality(args.commune)
    print(json.dumps(result, ensure_ascii=False, indent=2))
