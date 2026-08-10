#!/usr/bin/env python
"""Utilitaire en ligne de commande de Django pour Moléson."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django est introuvable. L'environnement virtuel est-il activé "
            "(ou la commande lancée dans le conteneur `app`) ?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
