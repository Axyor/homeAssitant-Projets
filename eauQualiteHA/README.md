# Intégration Home Assistant - Qualité de l'eau potable (Hub'Eau)

Ce projet permet d'afficher la qualité de l'eau potable de votre commune directement dans Home Assistant, grâce aux données ouvertes de l'API Hub'Eau (data.gouv.fr).

## Prérequis

- Un accès aux dossiers de configuration de votre Home Assistant (ex: via le module complémentaire File editor ou SSH).
- Avoir Python 3 installé sur l'environnement d'exécution (c'est le cas par défaut sur Home Assistant OS).
- Connaître le code INSEE de votre commune (qui est différent du code postal). [Recherchez votre code INSEE ici](https://www.insee.fr/fr/information/2028040).

## Installation

### 1. Mise en place du script Python

Home Assistant utilise par défaut un environnement Python capable d'exécuter des scripts simples.

- Allez dans le dossier racine de votre configuration Home Assistant (souvent `/config` ou `\homeassistant`).
- Créez un dossier dédié nommé `eau_qualite`.
- Placez-y le fichier `eau_qualite_script.py` tel quel. Le chemin complet devrait donc être : `/config/eau_qualite/eau_qualite_script.py`.
- Le script générera automatiquement un fichier cache local (ex: `eau_qualite_59328_cache.json`) ainsi qu'un fichier de log (`eau_qualite.log`) dans ce même dossier afin de limiter le nombre de requêtes à l'API en cas de données identiques.

### 2. Configuration du capteur (Sensor)

Pour intégrer les données collectées par le script, vous devez déclarer un capteur en ligne de commande.

- Ouvrez votre fichier `configuration.yaml` (ou le fichier dédié si vous avez scindé votre configuration).
- Copiez et collez **exactement** le contenu du fichier fourni `ha_config.yaml` à l'intérieur de `configuration.yaml`.
- **⚠️ Important :** Dans le code que vous venez de coller, repérez la ligne `command: "python3 ..."` et remplacez le code INSEE (ici `59328`) par celui de votre propre commune. _Attention : le code INSEE n'est pas votre code postal._ [Trouvez votre code INSEE ici](https://www.insee.fr/fr/information/2028040).

### 3. Redémarrage

- Vérifiez la syntaxe de votre configuration depuis les Outils de développement de Home Assistant.
- Redémarrez totalement votre instance Home Assistant pour que le capteur "Water Quality" (`sensor.water_quality`) apparaisse.

## Carte Dashboard

Vous pouvez utiliser le code YAML présent dans `dashboard_card.yaml` pour afficher une carte sur votre tableau de bord. Cette carte est basée sur [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom), il est donc recommandé de l'installer via HACS au préalable.

## Données fournies par le capteur (`sensor.water_quality`)

Le script remonte plusieurs attributs utiles consultables dans Home Assistant :

- `sampling_date` : Date de la dernière analyse effectuée
- `conclusion` : Conclusion sanitaire officielle textuelle
- `network` : Nom du réseau de distribution
- `bact_compliance` / `pc_compliance` : Indicateurs de conformité Bactériologique (bact) et Physico-Chimique (pc). "C" signifie Conforme.
- `hardness` : Titre hydrotimétrique (dureté de l'eau, indicateur de calcaire)
- `nitrates` : Taux de nitrates (important pour les nourrissons)
- `ph` : Potentiel en hydrogène
- `parameters` : Liste complète des mesures effectuées (pH, chlore, températures, bactéries, etc.) avec leurs valeurs, unités et seuils de référence. Vous pouvez utiliser une carte de type "markdown" dans Home Assistant pour iterer sur cet attribut et les afficher en tableau.
