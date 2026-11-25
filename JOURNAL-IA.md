# Journal d'usage de l'IA — PASSAGE

Ce journal rapporte les usages réellement effectués pendant le développement. Il ne présente pas une production vidéo ou un appel IA produit qui n'a pas eu lieu.

## Outils et usages

- **GitHub Copilot Chat (assistant de programmation utilisé dans VS Code), 24–25 novembre 2026 :** aide à la lecture des fichiers existants, propositions de corrections Django/DRF, modèles, vues, migrations, tests ciblés, interface React et documentation. Les changements ont été appliqués au dépôt puis vérifiés par les commandes listées ci-dessous.
- **Django 5.2.17 / Django REST Framework :** exécution des contrôles, génération de migrations et tests du backend.
- **SQLite :** base de développement utilisée par Django et base isolée créée par le runner de tests.
- **Vite, React et TypeScript :** compilation du frontend; `npm run build` a réussi après les changements d'interface.
- **Chromium via l'outil browser-automation :** vérification réelle que `agent` / `Test1234` atteint le tableau de bord puis se déconnecte sans erreur console ni requête échouée. Cette vérification a révélé le problème de routage/proxy et a guidé la correction.
- **GitHub Actions :** workflow présent dans le dépôt; le statut distant n'a pas été vérifié dans ce travail.

## Propositions refusées ou corrigées

1. **Ne pas déclarer une notification envoyée dès sa création.** Une première implémentation répondait `émis` après insertion en base, sans fournisseur appelé. Ce comportement a été remplacé par `pending`; le service de dispatch n'écrit `sent` et `sent_at` qu'après le retour réussi du fournisseur. Un échec est enregistré dans `failed` avec `last_error`.
2. **Ne pas créer un nouveau badge avant d'invalider l'actif.** Avec la contrainte « un badge actif par élève », l'ordre initial pouvait violer l'intégrité de la base. La réémission a été mise dans une transaction : révocation de l'ancien, création du nouveau puis lien historique `replaced_by`. Une relation unique nullable `active_student` rend cette garantie compatible SQLite/MySQL; une migration rétro-remplit les lignes déjà existantes.
3. **Corriger un test de limitation qui ne testait pas cinq échecs du même identifiant.** Le premier résultat était `200`, car le scénario avait réalisé quatre échecs sur `agent` et un autre sur un identifiant différent. Le test a été corrigé pour atteindre le seuil réel avant de vérifier le `429`.

## Vérifications réellement exécutées

- `python manage.py check` : réussi.
- `python manage.py makemigrations --check --dry-run` : aucune migration supplémentaire détectée après les migrations 0002 et 0003.
- `python manage.py test core` : 11 tests réussis.
- `python -m pytest -q` : 4 tests historiques réussis.
- `npm run build` : réussi pour le frontend React/TypeScript/Tailwind.
- Inspection du resolver Django : 25 routes listées, aucun pattern dupliqué.
- `python manage.py migrate --noinput` : migrations 0002 et 0003 appliquées après vérification que la cible était `django.db.backends.sqlite3` dans `backend/db.sqlite3`; aucune base de production/MySQL n'a été ciblée.
- Le scénario de synchronisation couvre un événement malformé dans un lot contenant un événement valide; le rejet n'empêche pas l'enregistrement de l'événement valide.
- Le frontend récupère le jeton CSRF Django et le transmet sur les requêtes authentifiées non sûres.

## Éléments non réalisés

- Aucun outil d'IA vidéo (CapCut, Descript, ElevenLabs ou équivalent) n'a encore été utilisé; les deux vidéos attendues restent à produire.
- Le backend Django utilise actuellement un gabarit exact pour les synthèses; aucun fournisseur LLM n'est appelé à l'exécution.
- Aucun fournisseur SMS/e-mail n'est configuré; les messages restent en file `pending` jusqu'à l'intégration d'un fournisseur.
