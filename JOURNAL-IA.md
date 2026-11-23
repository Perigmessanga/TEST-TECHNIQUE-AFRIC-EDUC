# Journal d'usage de l'IA

## Outils
- GitHub Copilot / assistant de programmation : architecture, FastAPI, SQLite, tests et documentation.

## Usages
- Génération du squelette API et des modèles Pydantic.
- Préparation des scénarios de tests et des scripts de données.
- Production assistée possible des scripts de démonstration et sous-titres de la capsule.

## Refus ou corrections
1. Une première proposition de mise en cache des jetons en mémoire a été corrigée : elle ne garantissait pas le consentement/restriction serveur. Le produit vérifie maintenant chaque jeton et son nonce avec HMAC côté SQLite.
2. Une correction de schéma avait initialement utilisé `TEXT NOT UNIQUE`, syntaxe invalide SQLite. Elle a été remplacée par `TEXT NOT NULL UNIQUE`.
