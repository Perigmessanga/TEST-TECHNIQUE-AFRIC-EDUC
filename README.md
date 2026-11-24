# PASSAGE — Smart School Attendance

Application de suivi hors ligne des passages d'élèves, développée avec React/TypeScript/Tailwind côté frontend et Django REST Framework côté backend.

## Stack

- Frontend : React, TypeScript, Vite, Tailwind CSS
- Backend : Django, Django REST Framework
- Développement : SQLite 3
- Production : MySQL via les variables d'environnement
- Authentification : sessions Django
- Interface : rôles agent, responsable et parent

## Lancer le backend

```powershell
cd backend
python -m pip install django djangorestframework django-cors-headers
python manage.py migrate
python seed.py
python manage.py runserver 127.0.0.1:8001
```

## Lancer le frontend

```powershell
cd frontend
npm install
npm run dev
```

Ouvrir http://127.0.0.1:5173.

## Comptes de test

- Responsable : `responsable` / `Test1234`
- Agent : `agent` / `Test1234`
- Parent : `parent1` / `Test1234`

## Base de données

SQLite est utilisé en développement. Pour MySQL, définir `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST` et `MYSQL_PORT`; Django bascule automatiquement vers MySQL lorsqu'une base est configurée.

## Sécurité

- Hachage Django des mots de passe
- Rôle vérifié côté serveur
- Session Django à durée limitée et déconnexion effective
- Accès parent limité aux élèves liés
- Badge HMAC tournant avec nonce unique et validité de 30 secondes
- Entrées REST validées
- ORM Django avec paramètres liés
- Secrets chargés depuis les variables d'environnement

## Validation

```powershell
cd backend
python manage.py check
cd ../frontend
npm run build
```

La CI GitHub Actions doit exécuter les contrôles Django et React à chaque envoi.

## Éléments livrés

- Interface responsive aux couleurs PASSAGE
- Connexion par rôle
- Interface agent hors ligne
- File locale de synchronisation
- Service Worker PWA prévu pour le mode hors ligne
- Détection des anomalies
- Synthèse IA avec gabarit de repli
- Consultation parent cloisonnée
- Historique Git régulier
