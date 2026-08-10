# Moléson

Plateforme de gestion de cours de l'Université populaire du canton de Fribourg
(Unipop/VHS) — bilingue FR/DE, API-first, remplaçante de Welante.

## Documents de référence

- `CLAUDE.md` — contexte projet chargé par Claude Code à chaque session
- `docs/correspondance-welante-moleson.md` — couverture fonctionnelle Welante → Moléson
- `docs/analyse-exports-welante.md` — analyse des données sources et implications schéma
- `docs/transition-claude-code.md` — guide d'installation et de travail avec Claude Code
- `docs/moleson-document-de-reference.pdf` — architecture, flux et phasage *(à déposer)*

## Données

Les exports Welante vont dans `data/` — **exclu de Git** (données personnelles, nLPD).
Voir `data/README.md`.

## Phasage

Phase 0 : validation Accounto (PDF QR via API) · Phase 1 : CRUD + API scopée +
bilinguisme · Portail formateurs · Phase 2 : facturation Accounto · Portail
participants · Phase 3 : dashboard, rappels, rapports, évaluations.
