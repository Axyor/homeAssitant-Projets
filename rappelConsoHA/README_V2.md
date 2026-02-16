# 🚨 Intégration RappelConso V2 pour Home Assistant

Surveille les rappels de produits dangereux (santé alimentaire, sécurité enfant, etc.) émis par le gouvernement français, en ciblant les produits de votre famille.

## ✨ Fonctionnalités

- 🔍 **Recherche multi-champs** — cherche dans le libellé, la sous-catégorie ET la marque
- 🆕 **Détection des nouveaux rappels** — cache intelligent, ne notifie que les nouveaux
- 📱 **Notifications enrichies** — nom du produit, marque, motif + image
- 🎨 **Dashboard Mushroom** — images, distributeurs, risques, conduite à tenir
- 📋 **Logging** — fichier `rappel.log` pour le diagnostic
- 🔄 **Mots-clés dynamiques** — modifiez `mots_cles.txt` sans redémarrer HA

## 📋 Pré-requis

- Accès aux fichiers de votre Home Assistant (Samba, File Editor ou VS Code)
- **Mushroom Cards** installé via HACS
- Python 3 (inclus par défaut dans HA OS/Container)

---

## 🛠 Étape 1 : Installation des fichiers

1. Créez un dossier `rappelConsoHA` dans `/config/`
2. Copiez-y les fichiers :
   - `rappel_script.py` — Le moteur
   - `mots_cles.txt` — Vos mots-clés

---

## ⚙️ Étape 2 : Configuration (Backend)

Ajoutez dans `configuration.yaml` :

```yaml
command_line:
  - sensor:
      name: Rappel Conso Ciblé
      command: "python3 /config/rappelConsoHA/rappel_script.py /config/rappelConsoHA/mots_cles.txt"
      value_template: "{{ value_json.count }}"
      json_attributes:
        - data
        - nouveaux
        - new_count
        - keywords_used
        - last_update
        - error
      scan_interval: 14400 # Toutes les 4 heures
      command_timeout: 30
```

### Template sensor (optionnel)

Pour un compteur dédié aux **nouveaux** rappels :

```yaml
template:
  - sensor:
      - name: "Rappel Conso Nouveaux"
        state: "{{ state_attr('sensor.rappel_conso_cible', 'new_count') | default(0) }}"
        icon: >-
          {% if states('sensor.rappel_conso_nouveaux') | int > 0 %}
            mdi:alert-decagram
          {% else %}
            mdi:shield-check
          {% endif %}
```

_Ajustez les chemins si votre dossier est placé ailleurs._

---

## 📋 Étape 3 : Mots-clés

Éditez `mots_cles.txt` (un par ligne, les lignes `#` sont ignorées) :

```text
# Alimentaire
fromage
saumon
# Enfants
jouet
# Électronique
pile
usb
```

Le script cherche ces mots dans le **libellé**, la **sous-catégorie** et la **marque** des produits rappelés.

---

## 🎨 Étape 4 : Dashboard

1. Allez sur votre Dashboard HA
2. Ajoutez une carte **Manuel**
3. Collez le contenu de `dashboard_card.yaml`

---

## 🔔 Étape 5 : Notifications (Optionnel)

Ajoutez dans `automations.yaml` (voir `ha_config_v2.yaml` pour le code complet) :

- Notification uniquement quand de **nouveaux** rappels apparaissent
- Message avec le détail de chaque produit (marque + titre + motif)
- Image du produit en pièce jointe

⚠️ **Remplacez** `notify.mobile_app_VOTRE_TELEPHONE` par votre service de notification.

---

## 📁 Fichiers générés automatiquement

| Fichier            | Rôle                                           |
| ------------------ | ---------------------------------------------- |
| `rappels_vus.json` | Cache des rappels déjà notifiés (auto-nettoyé) |
| `rappel.log`       | Logs du script (diagnostic)                    |

Pour le debug en ligne de commande :

```bash
python3 rappel_script.py --verbose
```

---

## 🔄 Redémarrage

1. **Outils de développement** > **YAML** > **Vérifier la configuration**
2. Si OK, redémarrez HA ou rechargez les entités "Command Line"
