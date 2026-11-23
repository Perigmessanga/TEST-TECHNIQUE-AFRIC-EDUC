# Passage — suivi hors ligne des élèves

Prototype FastAPI/SQLite pour le sujet B « Passage » d'Afric'Éduc.

## Installation

```powershell
python -m pip install -r requirements.txt
python seed.py
python -m uvicorn app.main:app --reload
```

Ouvrir http://127.0.0.1:8000.

## Comptes

Tous les mots de passe sont `Test1234` : `responsable`, `agent`, `parent1`, `parent2`.

## Tests

```powershell
python -m pytest -q
```

## Sécurité

Les mots de passe utilisent PBKDF2-SHA256 avec sel aléatoire, une longueur minimale de 8 caractères, une limitation à cinq essais et des erreurs d'identification identiques. Les cookies sont en HttpOnly avec expiration. Les rôles sont vérifiés côté API. La cloisonnement parent élève est appliquée par requête serveur. Les entrées Pydantic sont validées et SQLite reçoit des paramètres liés. Les sorties HTML sont sobres et les secrets sont dans des variables d'environnement. Les améliorations futures sont CSRF, rotation réelle des secrets, sessions Redis et durcissement HTTP.

## Badge

Le badge utilise un nonce aléatoire signé HMAC avec expiration à 30 secondes. Une photographie devient inutilisable après expiration ou consommation. Le modèle est basé sur `serial + expires + nonce + signature` sans identifier statiquement l'élève lisible sur le support.

## Mode dégradé

Sans `AI_API_KEY`, une synthèse exacte est produite par gabarit à partir des chiffres calculés en SQL. Une réponse IA est limitée à une nouvelle tentative, puis à ce gabarit. Les appels sont journalisés et plafonnés par `AI_MONTHLY_LIMIT`.

## Intégration continue

GitHub Actions installe Python, recharge les données de départ et exécute pytest à chaque push ou pull request.

## Non terminé

Interface hors ligne PWA complète, cron persistant, fournisseur SMS réel, interface responsable complète, tests Playwright et montage vidéo doivent être finalisés avant remise.
