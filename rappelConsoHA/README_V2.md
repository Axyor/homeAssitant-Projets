# 🚨 Intégration RappelConso "Ciblée" (V2) pour Home Assistant

Ce pack permet de surveiller les rappels de produits dangereux (santé alimentaire, sécurité enfant, etc.) émis par le gouvernement français, en ciblant spécifiquement les marques et produits consommés par votre famille.

## 📋 Pré-requis
- Accès aux fichiers de votre Home Assistant (via Samba, l'add-on "File Editor" ou "VS Code").
- Avoir installé **Mushroom Cards** via HACS (pour l'interface visuelle).
- Python 3 est déjà inclus par défaut dans Home Assistant (OS/Container).

---

## 🛠 Étape 1 : Installation des fichiers
1. Créez un dossier nommé `rappelConsoHA` dans votre répertoire `/config/` de Home Assistant.
2. Copiez-y les fichiers suivants :
   - `rappel_script.py` (Le moteur)
   - `mots_cles.txt` (Vos cibles)

---

## ⚙️ Étape 2 : Configuration du Capteur (Backend)
Ouvrez votre fichier `configuration.yaml` et ajoutez le code suivant :

```yaml
command_line:
  - sensor:
      name: Rappel Conso Cible
      # Le chemin /config/ est le standard pour HA
      command: "python3 /config/rappelConsoHA/rappel_script.py /config/rappelConsoHA/mots_cles.txt"
      value_template: "{{ value_json.count }}"
      json_attributes:
        - data
        - keywords_used
        - last_update
      scan_interval: 14400 # Vérification toutes les 4 heures
      command_timeout: 30
```
*Note : Si vous avez placé le dossier ailleurs, ajustez les chemins dans la ligne `command`.*

---

## 📋 Étape 3 : Gestion de vos mots-clés
Éditez le fichier `mots_cles.txt` pour y ajouter les produits ou marques à surveiller (un par ligne). 
*Exemple :*
```text
Bledina
Gallia
Fromage
Jouet
Kinder
```
Le script cherchera ces mots dans les titres des produits rappelés au cours des **14 derniers jours**.

---

## 🎨 Étape 4 : Création du Dashboard (Frontend)
1. Allez sur votre Dashboard Home Assistant.
2. Ajoutez une carte de type **Manuel** (tout en bas de la liste).
3. Copiez-collez le contenu intégral du fichier `dashboard_card.yaml`.

---

## 🔔 Étape 5 : Automatisation des notifications (Optionnel)
Pour être alerté sur votre téléphone dès qu'un produit familial est rappelé, ajoutez ceci dans `automations.yaml` :

```yaml
- alias: "[Sécurité Famille] Alerte Rappel Produit"
  trigger:
    - platform: state
      entity_id: sensor.rappel_conso_cible
  condition:
    # On ne notifie que si le nombre de rappels augmente
    - condition: template
      value_template: "{{ trigger.to_state.state | int > trigger.from_state.state | int }}"
  action:
    - service: notify.mobile_app_VOTRE_TELEPHONE # <--- À CHANGER
      data:
        title: "⚠️ ALERTE RAPPEL PRODUIT"
        message: "Un nouveau rappel correspond à vos critères familiaux."
        data:
          clickAction: "/lovelace/votre_page_rappels" # Lien vers votre dashboard
```

---

## 🔄 Redémarrage
Une fois tout configuré :
1. Allez dans **Outils de développement** > **YAML**.
2. Cliquez sur **Vérifier la configuration**.
3. Si tout est OK, redémarrez Home Assistant (ou rechargez les "Entités Command Line").