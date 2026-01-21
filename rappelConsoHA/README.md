# Intégration RappelConso pour Home Assistant

Ce dossier contient les éléments nécessaires pour intégrer les alertes du site officiel `rappel.conso.gouv.fr` dans votre instance Home Assistant.

## Contenu
1. `sensor_configuration.yaml` : Le code à ajouter dans votre `configuration.yaml`.
2. `lovelace_card.yaml` : Le code pour créer une carte d'affichage dans votre interface.

## Personnalisation
Pour changer les mots-clés de recherche, modifiez l'URL dans `sensor_configuration.yaml`.
La partie `where=search(libelle, "votre_mot_cle")` est celle à éditer.

Exemple pour chercher "jouet" :
`where=search(libelle, "jouet")`

Pour plusieurs mots-clés :
`where=search(libelle, "mot1") or search(libelle, "mot2")`

**Note :** N'oubliez pas de redémarrer Home Assistant ou de recharger les entités "REST" après avoir modifié le fichier de configuration.
