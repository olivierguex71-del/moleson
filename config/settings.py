"""Configuration Django de Moléson.

Un seul module de configuration, piloté par variables d'environnement (12-factor) :
il n'existe pas de `settings/dev.py` vs `settings/prod.py` à maintenir en parallèle.
Ce qui diffère entre les environnements se règle dans `.env`.
"""

from pathlib import Path

import environ
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# --- Sécurité --------------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
# La sonde de santé interroge l'application en boucle locale : son en-tête Host
# doit être accepté quel que soit le domaine servi (voir docker/healthcheck.py).
if "127.0.0.1" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("127.0.0.1")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Derrière Caddy, c'est le proxy qui termine TLS : Django doit le savoir pour que
# `request.is_secure()` réponde juste (cookies sécurisés, redirections).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# Clés de chiffrement des champs sensibles (No AVS des formateurs — nLPD).
# Voir apps/core/fields.py. La première clé chiffre, les suivantes déchiffrent
# l'existant lors d'une rotation.
MOLESON_ENCRYPTION_KEYS = env.list("MOLESON_ENCRYPTION_KEYS", default=[])

# --- Applications ----------------------------------------------------------

INSTALLED_APPS = [
    # Unfold doit précéder django.contrib.admin : il en remplace les gabarits.
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "apps.core",
    "apps.api",
    "apps.contacts",
    "apps.catalog",
    "apps.enrolments",
    "apps.communications",
    "apps.accounto",
    # Outillage de reprise des données Welante. Disparaîtra une fois la
    # migration faite et vérifiée.
    "apps.welante",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise sert les fichiers statiques depuis gunicorn en production, ce qui
    # évite de les partager avec Caddy par un volume. En développement, c'est
    # django.contrib.staticfiles qui s'en charge.
    *([] if DEBUG else ["whitenoise.middleware.WhiteNoiseMiddleware"]),
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
            ],
        },
    },
]

# --- Base de données -------------------------------------------------------

DATABASES = {"default": env.db("DATABASE_URL")}
# Connexions persistantes : à ce volume, inutile de rouvrir une connexion par requête.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DJANGO_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalisation --------------------------------------------------
#
# Moléson est bilingue de naissance : le français est la langue par défaut de
# l'interface, l'allemand est de plein droit. Le bilinguisme des *contenus*
# (title_fr / title_de) est une affaire de modèle, pas de configuration :
# voir apps/core/models.py.

LANGUAGE_CODE = "fr"
LANGUAGES = [
    ("fr", _("Français")),
    ("de", _("Deutsch")),
]
# Les deux seules langues dans lesquelles un contenu utilisateur peut exister.
CONTENT_LANGUAGES = ("fr", "de")

LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Europe/Zurich"
USE_I18N = True
USE_TZ = True

# --- Fichiers statiques et médias -----------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Le stockage « manifeste » empreinte chaque fichier statique pour un cache
# perpétuel côté navigateur. Il exige que `collectstatic` ait tourné : c'est le
# cas dans l'image de production, jamais en développement.
USE_STATIC_MANIFEST = env.bool("DJANGO_STATIC_MANIFEST", default=not DEBUG)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if USE_STATIC_MANIFEST
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# --- Email -----------------------------------------------------------------

globals().update(env.email_url("EMAIL_URL", default="consolemail://"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Moléson <noreply@unipopfr.ch>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# --- Journalisation --------------------------------------------------------
#
# nLPD : ne jamais journaliser de données personnelles. Les journaux vont sur la
# sortie standard, où Docker les collecte.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
}

# --- Intégration Accounto (Phase 0 / Phase 2) ------------------------------

ACCOUNTO_BASE_URL = env("ACCOUNTO_BASE_URL", default="")
ACCOUNTO_API_KEY = env("ACCOUNTO_API_KEY", default="")

# --- Administration (Unfold) ----------------------------------------------

UNFOLD = {
    "SITE_TITLE": "Moléson",
    "SITE_HEADER": "Moléson",
    "SITE_SUBHEADER": _("Université populaire du canton de Fribourg"),
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
}
