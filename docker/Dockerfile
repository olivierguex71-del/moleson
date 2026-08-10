# syntax=docker/dockerfile:1

# Image de base : Python 3.13 + uv fournis ensemble par Astral.
# Les dépendances système sont celles de WeasyPrint (Pango/HarfBuzz) — c'est ce
# moteur qui rend les PDF bilingues, wkhtmltopdf ayant été abandonné pour son
# Unicode peu fiable.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libfribidi0 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fonts-dejavu-core \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace


# --- Dépendances de production ---------------------------------------------
FROM base AS deps

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# --- Développement et tests -------------------------------------------------
# Le code est monté en volume : l'image ne contient que l'environnement.
FROM deps AS dev

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


# --- Production -------------------------------------------------------------
FROM base AS prod

COPY --from=deps /opt/venv /opt/venv
COPY . .

# Les fichiers statiques sont figés dans l'image : rien à collecter au démarrage.
# Les valeurs ci-dessous ne servent qu'à faire démarrer Django le temps de la
# commande — collectstatic ne touche pas la base.
RUN DJANGO_SECRET_KEY=build-only \
    DATABASE_URL=postgres://build:build@localhost:5432/build \
    python manage.py collectstatic --noinput --clear

RUN useradd --create-home --uid 10001 moleson \
    && mkdir -p /workspace/mediafiles \
    && chown -R moleson:moleson /workspace/mediafiles

USER moleson

EXPOSE 8000
ENTRYPOINT ["/workspace/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
