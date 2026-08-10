#!/bin/sh
# Point d'entrée du conteneur de production.
#
# Les migrations tournent ici plutôt que dans une étape de déploiement séparée :
# à l'échelle de Moléson, un seul conteneur applicatif démarre à la fois, et
# coupler migration et démarrage évite de servir du code en avance sur son schéma.
set -eu

echo "En attente de la base de données…"
until pg_isready --dbname "${DATABASE_URL}" --quiet; do
    sleep 1
done

echo "Application des migrations…"
python manage.py migrate --noinput

exec "$@"
