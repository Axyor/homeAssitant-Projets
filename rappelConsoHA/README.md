# 🚨 Intégration RappelConso V2 pour Home Assistant

Surveille les rappels de produits dangereux (santé alimentaire, sécurité enfant, etc.) émis par le gouvernement français, en ciblant les produits de votre famille.

## ✨ Fonctionnalités

- 🔍 **Recherche multi-champs** — cherche dans le libellé, la sous-catégorie, la marque ET le distributeur
- 🏪 **Filtrage par distributeur** — ne remonte que les rappels de vos magasins habituels
- 🛡️ **Mode surveillance** — produits critiques (bébé, santé) surveillés chez TOUS les distributeurs
- 🆕 **Détection des nouveaux rappels** — cache intelligent, ne notifie que les nouveaux
- 📱 **Notifications enrichies** — nom du produit, marque, motif + image
- 🎨 **Dashboard Mushroom** — images, distributeurs, risques, conduite à tenir
- 📋 **Logging** — fichier `rappel.log` pour le diagnostic
- 🔄 **Mots-clés dynamiques** — modifiez `mots_cles.txt` sans redémarrer HA

## 📋 Pré-requis

- Accès aux fichiers de votre Home Assistant (Samba, File Editor ou VS Code)
- **Mushroom Cards** installé via HACS (seule dépendance frontend requise, pas de `card-mod`)
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
        - distributeurs_used
        - surveillance_used
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

Éditez `mots_cles.txt` avec **3 sections** :

```text
[distributeurs]
# Magasins où vous faites vos courses
lidl
auchan
chronodrive

[surveillance]
# Produits critiques : surveillés chez TOUS les distributeurs
guigoz
compote
céréales bébé

[produits]
# Produits courants : filtrés par vos distributeurs uniquement
fromage
saumon
saumon fumé
lardons
jambon
oeuf
```

### Logique de filtrage

| Section           | Filtrage distributeur | Cas d'usage                         |
| ----------------- | :-------------------: | ----------------------------------- |
| `[distributeurs]` |           —           | Vos magasins habituels              |
| `[surveillance]`  |     ❌ Non filtré     | Produits critiques (bébé, allergie) |
| `[produits]`      |     ✅ Filtré AND     | Produits courants                   |

- **`[produits]`** → rappels remontés **uniquement** si le distributeur est dans votre liste
- **`[surveillance]`** → rappels remontés **quel que soit** le distributeur
- **Rétro-compatible** : un fichier sans sections `[...]` fonctionne comme avant (tout dans `[produits]`, pas de filtrage distributeur)

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

| Fichier | Rôle |
| --- | --- |
| `rappels_vus.json` | Cache des rappels déjà notifiés (auto-nettoyé) |
| `rappel_data_cache.json` | Dernier output complet — source de secours si l'API est indisponible |
| `rappel.log` | Logs du script (diagnostic) |

Pour le debug en ligne de commande :

```bash
python3 rappel_script.py --verbose
```

---

## 🔄 Redémarrage

1. **Outils de développement** > **YAML** > **Vérifier la configuration**
2. Si OK, redémarrez HA ou rechargez les entités "Command Line"

## Résilience & comportement hors-ligne

Le script tente jusqu'à **3 fois** d'appeler l'API RappelConso (délai de 5 s entre chaque essai) avant de passer en mode dégradé.

| Type d'erreur | Comportement |
|---|---|
| Timeout, réseau coupé (`URLError`) | Retry |
| Erreur serveur 5xx | Retry |
| Erreur client 4xx | Pas de retry |
| Réponse JSON invalide | Retry |

En cas d'échec total, le capteur retourne les **dernières données issues du cache** (`rappel_data_cache.json`), enrichies de :

| Attribut | Type | Description |
|---|---|---|
| `stale` | `bool` | `true` si les données proviennent du cache de secours |
| `stale_since` | `string` (ISO 8601) | Horodatage du premier échec ayant déclenché le mode dégradé |
| `new_count` | `int` | Toujours `0` en mode stale (pas de re-notification) |

Si aucun cache n'est disponible (première exécution), le capteur retourne une erreur classique avec `stale: false`.
