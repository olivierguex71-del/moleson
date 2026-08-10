#!/usr/bin/env python
"""Sonde de santé du conteneur applicatif.

Interroge l'application depuis l'intérieur du conteneur, en boucle locale. Deux
précautions, sans lesquelles la sonde échouerait en permanence en production :

- `X-Forwarded-Proto: https` — sinon Django répond 301 vers HTTPS (voir
  SECURE_SSL_REDIRECT), et la sonde suivrait une redirection vers un port qui
  n'écoute pas ;
- l'en-tête `Host` doit être accepté par ALLOWED_HOSTS, qui inclut toujours
  l'adresse de boucle locale à cette fin.

Le conteneur n'est déclaré sain que si la base est joignable : servir des pages
d'erreur avec une base coupée ne mérite pas le label « healthy ».
"""

import json
import sys
import urllib.request

URL = "http://127.0.0.1:8000/api/v1/health"

try:
    request = urllib.request.Request(URL, headers={"X-Forwarded-Proto": "https"})
    # L'URL est une constante en boucle locale, jamais une entrée externe.
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        payload = json.load(response)
        sain = response.status == 200 and payload.get("database") == "ok"
except Exception as exc:
    # Toute erreur — connexion refusée, délai dépassé, réponse illisible —
    # signifie « pas sain » : c'est précisément ce que la sonde doit rapporter.
    print(f"healthcheck: {exc}", file=sys.stderr)
    sys.exit(1)

sys.exit(0 if sain else 1)
