# Décisions techniques — PASSAGE

Choix effectivement matérialisés dans le dépôt. Les limites ci-dessous sont explicites et ne sont pas déclarées comme des fonctions terminées.

## 1. Stack et séparation

- **Retenu :** React/TypeScript/Vite/Tailwind et Django REST Framework.
- **Écarté :** poursuivre le prototype FastAPI et son écran HTML.
- **Raison :** utiliser le stack demandé et séparer interface, API et persistance.

## 2. Base de données

- **Retenu :** SQLite en développement; sélection MySQL par variables `MYSQL_*` en déploiement.
- **Écarté :** exiger un serveur MySQL pour chaque lancement local.
- **Raison :** installation locale reproductible. Les migrations sont présentes, mais la configuration MySQL n'a pas été validée sur une instance de production.

## 3. Identité et génération des QR

- **Retenu :** QR temporaire contenant un serial opaque, une expiration, un nonce et une signature HMAC; génération réservée au responsable; consommation du nonce une seule fois.
- **Écarté :** QR statique contenant l'identifiant ou le nom de l'élève.
- **Raison :** réduire la réutilisation et ne pas exposer l'identité dans le QR. Le TTL de huit heures par défaut sert le fonctionnement sur une journée sans réseau.
- **Limite :** une copie du QR peut gagner la course au tout premier usage; l'usage unique empêche les réutilisations ultérieures, mais ne prouve pas l'appareil source. L'anti-copie absolu demande un challenge connecté ou une attestation matérielle.

## 4. Historique et réémission des badges

- **Retenu :** plusieurs enregistrements historiques via `ForeignKey`; un champ unique nullable réserve le badge actif par élève; la réémission révoque l'ancien, crée le nouveau et garde `replaced_by` dans une transaction.
- **Écarté :** écraser l'ancien badge ou supprimer son historique.
- **Raison :** invalider le secret précédent et conserver la piste de réémission. Migrations `0002` et `0003`.

## 5. Synchronisation et horloge

- **Retenu :** identifiant d'événement et nonce uniques en base; heure locale conservée, heure serveur utilisée comme référence; écart supérieur à une heure signalé comme anomalie `horloge_appareil`.
- **Écarté :** rejeter la présence ou faire confiance à l'horloge de l'agent.
- **Raison :** conserver l'événement et signaler l'incertitude sans laisser l'horloge du téléphone déterminer les statistiques. La file navigateur reste locale jusqu'à synchronisation.

## 6. Détection des anomalies et absence

- **Retenu :** anomalies de point inattendu, passage hors fenêtre, double scan à moins de 60 secondes et horloge décalée lors de la synchronisation; détection des absences échues via endpoint et commande `python manage.py detect_absences`.
- **Écarté :** prétendre qu'un ordonnanceur est déjà installé ou lancer la détection uniquement à l'ouverture du tableau de bord.
- **Raison :** rendre le traitement d'absence répétable et idempotent. La commande doit encore être planifiée par l'exploitant (Task Scheduler/cron); aucun ordonnanceur n'est provisionné par le dépôt.

## 7. Notifications aux parents

- **Retenu :** boîte de sortie dédupliquée parent/anomalie, plafond quotidien, états `pending`, `sending`, `sent`, `failed`, `suppressed`; commande d'envoi SMTP explicite et adaptateur testable.
- **Écarté :** annoncer qu'un message est livré lorsqu'il vient seulement d'être enregistré.
- **Raison :** distinguer la mise en file de la remise au serveur de courrier. Sans SMTP configuré, le message reste `pending`; l'envoi réel n'a pas été testé.

## 8. Permissions et données enfants

- **Retenu :** rôles contrôlés dans Django; les parents ne voient que les élèves liés via `ParentStudent`; le responsable peut gérer ces liens; l'agent n'a pas accès aux anomalies, messages ou statistiques.
- **Écarté :** faire reposer les droits sur le seul masquage d'éléments React.
- **Raison :** protéger aussi les appels API directs et les identifiants modifiés dans l'URL.

## 9. Synthèse quotidienne assistée

- **Retenu :** backend calcule les quatre nombres depuis passages/itinéraires; gabarit exact sans clé; appel optionnel compatible OpenAI avec sortie JSON, contrôle strict des chiffres, une nouvelle tentative maximum, journal `AICall` et plafond journalier.
- **Écarté :** laisser le modèle compter ou accepter un texte numérique non vérifié.
- **Raison :** préserver l'exactitude et continuer sans réseau/clé. Le fournisseur réel n'a pas été appelé pendant les validations faute de clé de test; son comportement réseau n'est donc pas certifié en production.

## 10. Création des comptes parent en nombre

- **Retenu :** le responsable peut créer un parent et rattacher plusieurs enfants, ou importer les rattachements depuis un CSV; les nouveaux comptes reçoivent un mot de passe temporaire aléatoire et doivent le changer à la première connexion.
- **Écarté :** créer tous les parents avec un mot de passe commun ou leur permettre de consulter les données avant de changer le mot de passe temporaire.
- **Raison :** réduire le travail manuel pour les grands effectifs et éviter un secret initial partagé. Les mots de passe temporaires ne sont exposés qu'à la création et doivent être transmis par un canal privé.
