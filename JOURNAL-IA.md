# Journal d'usage de l'intelligence artificielle — PASSAGE

Journal rédigé pour les travaux réellement présents dans le dépôt. Les intégrations externes non configurées ne sont pas déclarées comme testées.

## Outils utilisés

- **GitHub Copilot Chat , 24–25 novembre 2026 :**  aide à la correction Django/DRF, création des migrations/tests, implémentation d'API et composants React, revues des erreurs TypeScript/Django et rédaction des décisions/documentation. Le code a été relu et vérifié par commandes locales.
- **Django 5.2 / Django REST Framework :** `manage.py check`, tests API, commandes de migrations et commande de détection d'absences.
- **SQLite :** base de test Django et base de développement; aucune migration de production n'a été exécutée.
- **React, TypeScript, Vite et Tailwind :** interface par rôle, scan caméra QR (html5-qrcode), génération QR (qrcode.react), file offline, actions de gestion, build et ESLint.
- **React et Django :** diagnostic caméra distinguant origine non sécurisée, API caméra absente, permission refusée, caméra absente ou déjà utilisée; création/import de comptes parent et réinitialisation contrôlée d'un mot de passe temporaire perdu.
- **GitHub Actions :** workflow configuré pour exécuter les tests Python/Django, ESLint et le build frontend sur push et pull request. La dernière exécution distante consultée est verte pour le commit précédent; le changement actuel n'est pas encore poussé et devra déclencher une nouvelle exécution.
- **Aucune IA vidéo n'a été utilisée dans ce passage de travail.** Les deux vidéos attendues restent à produire séparément et devront être ajoutées au journal avec les outils réellement utilisés.
- **Capcut :** pour la realisation de la video capsule de communication et demonstration technique.

## Refus et corrections motivés

1. **Ne pas déclarer une notification envoyée après sa seule insertion en base.** Le statut a été conservé en `pending`; la transition vers `sent` et l'heure `sent_at` n'arrivent qu'après acceptation par le provider. L'absence de fournisseur SMTP laisse les notifications en attente.
2. **Ne pas confier les statistiques au modèle.** Les effectifs, présences, retards et sorties hors plage sont calculés par Django. La sortie IA est contrainte à un objet JSON et rejetée si ses chiffres diffèrent; une seule nouvelle tentative précède le gabarit exact.
3. **Ne pas conserver la courte expiration de 30 secondes pour la file hors ligne.** Elle rendrait les événements collectés sans réseau invalides au retour de connexion. Le TTL est configurable et fixé à huit heures par défaut pour une journée de service; cette amélioration n'élimine pas le risque de course à la première utilisation d'un QR copié, explicitement documenté dans `DECISIONS.md`.
4. **Ne pas annoncer qu'une absence est détectée automatiquement au moment de la clôture sans ordonnanceur.** Une commande Django idempotente est fournie; l'horaire Task Scheduler/cron reste à configurer sur le serveur qui l'hébergera.
5. **Ne pas confondre compilation réussie et absence de défaut visuel.** Les écrans ont été étoffés et compilent; un parcours navigateur complet couvrant les trois rôles et le scan caméra n'a pas été effectué dans cette session.
6. **Ne pas réutiliser un secret parent commun pour un import massif.** Chaque nouveau compte reçoit un secret temporaire aléatoire et doit le changer à la première connexion; le CSV d'import ne contient pas de mot de passe.
7. **Ne pas diagnostiquer tous les échecs caméra comme un problème HTTPS.** `localhost` est normalement un contexte sécurisé; le composant distingue désormais l'origine non sécurisée des permissions navigateur et des caméras indisponibles.
8. **Ne pas faire croire qu'un parent nouveau reçoit le mot de passe commun de démonstration.** L'identifiant est un nom d'utilisateur choisi; le mot de passe est aléatoire. Le résultat distingue les comptes créés des parents déjà existants, et le responsable dispose d'une action de réinitialisation qui remet l'obligation de changement au prochain accès.

## Vérifications réellement exécutées pendant l'implémentation

- `python backend/manage.py check` : réussi.
- `python backend/manage.py makemigrations --check --dry-run` : aucune migration manquante après création de `0004_profile_must_change_password`.
- `python backend/manage.py test core` : 21 tests réussis, notamment rôles, cloisonnement parent, création/import des comptes parents, changement obligatoire du mot de passe temporaire, réémission/nonce, anomalies, file de notifications, comptage de synthèse et idempotence de la commande d'absence.
- `python -m pytest -q` : 4 tests historiques réussis.
- `npm run build` depuis `frontend` : réussi avec TypeScript; le lecteur caméra est produit dans un chunk différé distinct.
- `npm run lint` depuis `frontend` : réussi sans erreur ni avertissement.
- Le test de build ne remplace ni le test réel des autorisations caméra sur mobile ni un test réseau hors ligne multi-appareils.

## Ce qui reste à tracer après livraison

- Un appel à un fournisseur LLM avec clé de test et vérification des coûts/réponses; en attendant, seul le gabarit est garanti en environnement local.
- L'envoi SMTP réel; les commandes d'envoi existent, mais il faut configurer les secrets et une adresse joignable.
- Le résultat GitHub Actions du commit contenant les changements de cette session, à contrôler après le push.
- Enregistrement/montage de la démonstration technique et de la capsule communication, puis insertion des outils réellement utilisés et des liens partageables.
- Essai de caméra sur le navigateur/appareil du candidat : l'erreur était auparavant générique; le message est désormais plus précis, mais aucun contrôle distant de la permission caméra n'est possible depuis le dépôt.
