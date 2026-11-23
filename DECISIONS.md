# Décisions techniques

1. **Backend** — FastAPI/SQLite, plutôt que NestJS/PostgreSQL. Option retenue pour sa légèreté locale; écartée: Django/PostgreSQL, plus lourd à déployer en cinq jours.
2. **Badge** — nonce aléatoire signé HMAC avec validité de 30 secondes, plutôt qu'un identifiant statique.
3. **Photographie du badge** — elle est inutilisable : le nonce expire rapidement et est consommé une seule fois.
4. **Contrainte agent** — l'agent doit être en ligne au moins toutes les 30 secondes pour obtenir un jeton à afficher. Repli hors ligne basé sur synchronisation différée, pas sur validation hors ligne permanente.
5. **Idempotence** — clé unique `local_event_id` et `nonce` côté serveur; les lots rejoués deviennent des doublons comptés.
6. **Horloge** — rejet si l'écart entre heure locale et heure serveur dépasse 60 minutes; l'événement reste visible parmi les rejets synchronisation.
7. **Détection d'absence** — tâche planifiée/endpoint déclenché périodiquement à la clôture des fenêtres. En production, Celery/cron remplacera l'appel manuel.
8. **Cinquième anomalie** — double scan à moins de 60 secondes. Justification: risque de comptage frauduleux ou accidentel sans donnée extérieure.
9. **Notifications** — file de sortie avec interface fournisseur, plutôt qu'appel SMS direct.
10. **IA** — JSON calculé côté serveur, appel optionnel, gabarit exact sans clé. Sortie validée puis nouvelle tentative unique.
