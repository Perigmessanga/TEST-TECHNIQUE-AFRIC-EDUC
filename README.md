# PASSAGE — Smart School Attendance

Application de suivi des passages d'élèves par QR, avec espaces Agent, Responsable et Parent. Stack : React + TypeScript + Vite + Tailwind CSS, API Django REST Framework, SQLite en développement et configuration MySQL par variables d'environnement.

## Démarrage local (Windows / PowerShell)

Depuis la racine du dépôt, dans un premier terminal :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Set-Location backend
python manage.py migrate
python seed.py
python manage.py runserver 127.0.0.1:8001
```

`seed.py` réinitialise les données PASSAGE de la base configurée : l'utiliser uniquement sur une base locale jetable ou avant d'avoir des données à conserver.

Dans un second terminal :

```powershell
Set-Location frontend
npm ci
npm run dev
```

Ouvrir l'adresse locale annoncée par Vite (port 5173 par défaut). Le proxy Vite transmet `/api` à Django; ne pas ouvrir directement le backend pour utiliser l'interface.

Pour la caméra, ouvrez exactement `http://localhost:5173` ou `http://127.0.0.1:5173` sur la machine qui exécute le navigateur. Les adresses LAN telles que `http://192.168.x.x:5173` ne sont pas des origines localhost sécurisées et nécessitent HTTPS. Si l'origine est correcte, autorisez la caméra dans le navigateur, fermez les autres applications qui l'utilisent puis rechargez la page; l'interface affiche le motif précis du refus.

## Comptes de démonstration

| Rôle | Identifiant | Mot de passe |
|---|---|---|
| Responsable | `responsable` | `Test1234` |
| Agent | `agent` | `Test1234` |
| Parent | `parent1` | `Test1234` |
| Parent | `parent2` | `Test1234` |

Les comptes et données d'exemple ne sont pas des identifiants de production.

## Parcours fonctionnels

- **Agent :** choisit un point, lit le QR avec la caméra ou saisit le jeton, conserve les événements dans `localStorage`, affiche l'état de synchronisation et synchronise à la reconnexion. La file accepte les lots/reprises; les événements rejetés sont laissés visibles pour correction.
- **Responsable :** crée/modifie les élèves, crée les comptes parents et rattache un ou plusieurs enfants, importe des milliers de rattachements depuis CSV, crée des points et itinéraires, ajoute des exceptions, génère des QR temporaires, réémet/suspend/réactive/révoque les badges, consulte les passages, détecte les absences échues, traite les anomalies, gère les notifications en file et génère une synthèse par classe/date.
- **Parent :** voit uniquement ses enfants liés, leurs passages, anomalies et notifications enregistrées.

### Création et rattachement des parents

Dans **Responsable → Élèves**, le formulaire permet de créer un compte parent et de sélectionner plusieurs enfants. Le mot de passe temporaire est généré aléatoirement, affiché une seule fois après création et doit être transmis au parent par un canal privé. Le parent doit le remplacer par un mot de passe d'au moins 12 caractères à sa première connexion.

Pour un import en lot, téléchargez d'abord la liste des élèves afin d'obtenir leurs identifiants, puis le modèle CSV. Les colonnes attendues sont `parent_username,parent_email,first_name,last_name,student_id`; répétez une ligne avec le même `parent_username` pour rattacher plusieurs enfants à un parent. Un compte parent déjà existant est réutilisé sans modifier son mot de passe. Les identifiants temporaires des nouveaux comptes sont retournés une seule fois et peuvent être téléchargés immédiatement; protégez ce fichier et supprimez-le après transmission.

## Migrations et bases

SQLite est sélectionné par défaut. Django choisit MySQL si `MYSQL_DATABASE` est défini; fournir également `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST` et `MYSQL_PORT`. `mysqlclient` est dans les dépendances.

Créer et relire les migrations avant déploiement :

```powershell
Set-Location backend
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

Appliquer explicitement les migrations uniquement après sauvegarde et validation de l'environnement ciblé :

```powershell
python manage.py migrate
```

Aucun démarrage de l'application ne lance de migration automatiquement.

## Fonctionnement planifié et notifications

Après la clôture des fenêtres de passage, exécuter périodiquement :

```powershell
python manage.py detect_absences
```

Pour livrer les messages par SMTP, configurer `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` et `DEFAULT_FROM_EMAIL`, puis lancer :

```powershell
python manage.py dispatch_notifications
```

Sans SMTP, les messages restent `pending`; la file ne prétend pas qu'ils sont envoyés. Ces commandes ne sont pas lancées par un ordonnanceur inclus dans le projet : il faut les planifier sur le serveur (Task Scheduler/cron) si un traitement automatique est requis.

## Synthèse assistée (optionnelle)

Sans clé, le gabarit local exact reste disponible. Pour autoriser l'appel optionnel à une API compatible OpenAI, définir `OPENAI_API_KEY`, éventuellement `OPENAI_MODEL` et `OPENAI_BASE_URL`, ainsi que les tarifs `AI_INPUT_USD_PER_MILLION` / `AI_OUTPUT_USD_PER_MILLION` et le plafond quotidien `AI_DAILY_COST_LIMIT`. Le backend envoie uniquement des compteurs agrégés, valide le JSON et les chiffres, retente une fois, journalise chaque tentative dans `AICall` et revient au gabarit si la sortie échoue. Une synthèse identique déjà calculée n'est pas refacturée.

L'intégration n'a pas été vérifiée contre un fournisseur réel sans clé; le mode de repli est le comportement de base.

## Sécurité et limites à connaître

- Mots de passe hachés par Django; session d'une heure, déconnexion et jeton CSRF.
- Permissions vérifiées sur les vues API; cloisonnement parent/enfants effectué au serveur.
- Limitation des tentatives de connexion paramétrable avec `LOGIN_FAILURE_LIMIT` et `LOGIN_FAILURE_WINDOW_SECONDS`.
- Les jetons QR sont signés HMAC, à usage unique et expirent après `BADGE_TOKEN_TTL_SECONDS` (8 heures par défaut pour permettre un lot hors ligne sur une journée). Les scans utilisent l'heure de réception serveur pour les anomalies; un décalage d'horloge est signalé.
- **Limite sécurité/offline :** un QR préémis hors ligne ne peut pas prouver quel écran l'a présenté. Son nonce empêche un second usage après synchronisation, mais une copie peut gagner la course au tout premier usage avant le vrai badge. Pour garantir une liaison à l'appareil source, il faut un mécanisme challenge-réponse connecté ou du matériel/attestation supplémentaire; ne pas présenter cette version comme une protection anti-copie absolue.
- Le cache PWA porte sur les ressources Web, pas sur les réponses API. Il faut ouvrir l'application et charger le lecteur caméra avant la coupure réseau.
- Le test local ne remplace pas un audit de sécurité ni un test sur un serveur MySQL.

## Tests et intégration continue

```powershell
python -m pytest -q
Set-Location backend
python manage.py check
python manage.py test core
Set-Location ..\frontend
npm ci
npm run lint
npm run build
```

GitHub Actions exécute les tests historiques, les contrôles/tests Django, les migrations sur sa base CI éphémère, ESLint puis le build React à chaque `push` et `pull_request`. Vérifier l'état réel du workflow sur GitHub après le push avant de transmettre le lien du dépôt.

## Livrables vidéo

Les vidéos de démonstration technique (≤ 6 min) et capsule de communication (60–90 s) sont des livrables séparés à enregistrer, monter et héberger. Elles ne sont pas produites par le dépôt.
