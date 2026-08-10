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
