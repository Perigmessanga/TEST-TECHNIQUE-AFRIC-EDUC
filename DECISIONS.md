# Décisions techniques — PASSAGE

Ce document décrit les choix effectivement présents dans le dépôt au 25 novembre 2026. Les éléments indiqués comme limites ne sont pas présentés comme terminés.

## 1. Stack applicative

- **Option retenue :** React, TypeScript, Vite et Tailwind pour l'interface; Django REST Framework pour l'API.
- **Option écartée :** FastAPI et un frontend HTML servi par le backend.
- **Raison :** retenir les technologies que je peux maintenir et expliquer pendant la restitution. Le prototype FastAPI a été remplacé par Django/React; Django utilise les modèles ORM, l'authentification et les migrations.

## 2. Bases de données

- **Option retenue :** SQLite en développement; paramètres Django prévus pour MySQL quand les variables `MYSQL_*` sont renseignées.
- **Option écartée :** imposer MySQL aux développeurs dès le démarrage.
- **Raison :** rendre l'installation locale reproductible sans service externe. Le mode MySQL est configuré mais n'a pas été validé contre un serveur MySQL dans ce dépôt.

## 3. Badge et copie photographiée

- **Option retenue :** identifiant opaque, nonce aléatoire signé par HMAC, expiration de 30 secondes et consommation unique côté serveur.
- **Option écartée :** QR statique contenant l'identifiant de l'élève.
- **Raison :** le QR temporaire copié expire et un nonce déjà utilisé est refusé. L'endpoint de création de jeton est réservé au responsable; un fournisseur ou mécanisme de lecture QR caméra n'est pas encore intégré à l'interface.

## 4. Réémission de badge

- **Option retenue :** conserver chaque ancien badge, révoquer l'actif et créer le remplaçant dans une transaction; l'ancien pointe vers `replaced_by`. Le champ unique nullable `active_student` réserve l'élève uniquement au badge actif.
- **Option écartée :** mettre à jour le même enregistrement ou supprimer l'ancien badge.
- **Raison :** préserver l'historique et invalider l'ancien secret. La relation unique nullable garantit au plus un badge actif sur SQLite comme sur MySQL; la migration 0003 rétro-remplit les badges actifs existants.

## 5. Synchronisation et horloge

- **Option retenue :** identifiant local d'événement unique et nonce unique; le serveur horodate la réception et rejette une heure locale écartée de plus d'une heure.
- **Option écartée :** faire confiance à l'horloge de l'appareil ou créer un nouveau passage à chaque renvoi.
- **Raison :** permettre le rejeu sans doublon et détecter les horloges manifestement fausses. La file locale React est stockée sur l'appareil; l'expiration courte du QR rend toutefois l'usage de scans acquis hors ligne limité et nécessite une évolution avant une vraie exploitation terrain.

## 6. Détection des absences

- **Option retenue :** endpoint Django de détection idempotent qui ignore les journées avec exception et crée l'anomalie une seule fois.
- **Option écartée :** lancer la détection uniquement à l'ouverture du tableau de bord, ou prétendre qu'une tâche automatique est déjà déployée.
- **Raison :** séparer la logique serveur. **Limite :** aucun ordonnanceur/cron n'appelle actuellement cet endpoint automatiquement; la détection doit être déclenchée par un responsable.

## 7. Notifications aux parents

- **Option retenue :** boîte de sortie persistante, unique par parent/anomalie, avec états `pending`, `sending`, `sent`, `failed` et `suppressed`; plafond journalier configurable.
- **Option écartée :** marquer immédiatement un message comme envoyé lors de sa simple création.
- **Raison :** distinguer la mise en file de la livraison réelle. L'adaptateur fournisseur enregistre les erreurs et permet une nouvelle tentative; aucun service SMS/e-mail externe n'est configuré. Le message nouvellement créé reste donc `pending`, pas `sent`.

## 8. Cloisonnement par rôle

- **Option retenue :** vérifier le profil de rôle dans les vues API; filtrer les élèves, passages, anomalies et messages du parent côté serveur; refuser les statistiques à l'agent.
- **Option écartée :** masquer uniquement les pages ou boutons dans React.
- **Raison :** un changement d'identifiant ou un appel direct à l'API ne doit pas outrepasser les droits. Les tests couvrent les refus agent et l'accès parent croisé.

## 9. Synthèse quotidienne

- **Option retenue :** chiffres calculés par le backend et phrase exacte produite par gabarit local.
- **Option écartée :** laisser un modèle inventer ou compter les chiffres sans contrôle.
- **Raison :** garantir l'exactitude même sans clé ni réseau. **Limite :** aucun appel à un modèle de langage n'est actuellement réalisé par le backend Django; l'intégration IA produit reste à ajouter.
