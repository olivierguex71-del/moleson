# Moléson

Plateforme de gestion de cours de l'Université populaire du canton de Fribourg
(Unipop/VHS) — bilingue FR/DE, API-first, remplaçante de Welante.

## Stack

| Couche | Choix |
|---|---|
| Backend | Django 5.2 LTS (Python 3.13) |
| API | django-ninja — OpenAPI publié sur `/api/v1/docs` |
| Base de données | PostgreSQL 17 (`unaccent`, `pg_trgm`) |
| Administration | Django admin habillé par Unfold, écrans sur mesure en HTMX |
| PDF | WeasyPrint |
| Déploiement | Docker Compose sur VPS — Caddy (TLS) · gunicorn · PostgreSQL |

## Démarrage

Prérequis : Docker. Rien d'autre — ni Python ni PostgreSQL sur la machine.

```bash
cp .env.example .env          # puis générer les clés (instructions dans le fichier)
docker compose up             # http://localhost:8000
```

Créer un compte d'administration :

```bash
docker compose run --rm app python manage.py createsuperuser
```

L'administration est sur `/admin/`, le contrat de l'API sur `/api/v1/docs`.

VS Code ouvre le projet directement dans le conteneur (« Reopen in Container ») :
la configuration est dans `.devcontainer/`, et s'appuie sur le même `compose.yaml`.

## Commandes courantes

```bash
docker compose run --rm app pytest              # tests
docker compose run --rm app ruff check .        # lint
docker compose run --rm app ruff format .       # formatage
docker compose run --rm app python manage.py makemigrations
docker compose run --rm app python manage.py migrate
```

Après modification de `pyproject.toml`, régénérer le verrou puis reconstruire :

```bash
docker compose run --rm app uv lock
docker compose build app
```

## Migration depuis Welante

À faire sur la machine où se trouvent les exports, `data/` étant recopié à la main.

```bash
# 1. Décrire les fichiers présents — n'affiche aucune donnée personnelle,
#    la sortie peut être copiée dans un message sans précaution.
docker compose run --rm app python manage.py welante_inspect

# 2. Créer les régions et les types d'adhésion (idempotent).
docker compose run --rm app python manage.py seed_reference

# 3. Simuler l'import : tout est exécuté, puis annulé.
docker compose run --rm app python manage.py welante_import --report data/anomalies.csv

# 4. Importer réellement, une fois le rapport lu.
docker compose run --rm app python manage.py welante_import --commit
```

Si `welante_inspect` signale des colonnes non reconnues, ajouter leur intitulé
aux alias dans `apps/welante/sources.py` — c'est le seul endroit à ajuster.

Trois garde-fous à connaître :

- **la simulation écrit puis annule**, elle éprouve donc les vraies contraintes
  de la base ; un import qui passe en simulation passera pour de bon ;
- **le rapport ne recopie jamais une valeur du fichier source** : il désigne une
  ligne et une colonne, pour ne pas devenir un second exemplaire des données ;
- **l'import refuse de démarrer sans `MOLESON_ENCRYPTION_KEYS`** quand il doit
  traiter les numéros AVS des intervenants.

## Documents de référence

- `CLAUDE.md` — contexte projet chargé par Claude Code à chaque session
- `docs/correspondance-welante-moleson.md` — couverture fonctionnelle Welante → Moléson
- `docs/analyse-exports-welante.md` — analyse des données sources et implications schéma
- `docs/transition-claude-code.md` — guide d'installation et de travail avec Claude Code
- `docs/moleson-document-de-reference.pdf` — architecture, flux et phasage *(à déposer)*

## Données

Les exports Welante vont dans `data/` — **exclu de Git** (données personnelles, nLPD).
Voir `data/README.md`. Aucune donnée personnelle réelle ne doit apparaître dans les
tests, fixtures, seeds ou journaux.

Les numéros AVS des formateurs sont chiffrés au repos par `apps/core/fields.py` :
les clés vivent dans `.env` (`MOLESON_ENCRYPTION_KEYS`) et **les perdre rend les
données définitivement illisibles**. Les sauvegarder séparément des sauvegardes de
base de données.

## Phasage

Phase 0 : validation Accounto (PDF QR via API) · Phase 1 : CRUD + API scopée +
bilinguisme · Portail formateurs · Phase 2 : facturation Accounto · Portail
participants · Phase 3 : dashboard, rappels, rapports, évaluations.
