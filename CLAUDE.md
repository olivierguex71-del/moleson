# CLAUDE.md — Projet Moléson

## Contexte

Moléson est une plateforme de gestion de cours pour l'Université populaire du canton de Fribourg (Unipop/VHS), destinée à remplacer l'outil tiers Welante. Contexte bilingue français/allemand natif. Le nom vient du sommet fribourgeois Le Moléson.

Différenciateurs vs Welante : ouvert, propriétaire de ses données, API-first, modulaire. Welante est fermé, sans API publique, mal localisé, avec extensions payantes.

## Conventions

- `moleson` (sans accent) pour tous les identifiants techniques ; « Moléson » (avec accent) pour le branding et les contenus.
- Bilinguisme par champ : chaque contenu utilisateur existe en FR et DE (`title_fr`, `title_de`, etc.). Jamais de concaténation des deux langues dans un champ (c'est l'anti-pattern Welante).
- Chaque contact a une langue de correspondance (fr/de) ; toute communication sortante est envoyée dans cette langue.
- Communiquer avec Olivier en français.

## Architecture & phasage

- **Phase 0** : validation Accounto en staging — confirmer que l'API expose le PDF QR-facture conforme (pas seulement l'UI). Prérequis avant développement complet.
- **Phase 1** : CRUD complet de toutes les entités, bilinguisme natif, fondation API avec authentification et scoping des permissions dès le départ (même si l'admin est le seul consommateur initial).
- **Portail formateurs** : juste après Phase 1 (présences, listes imprimables) — test du modèle d'API scopée.
- **Phase 2** : facturation et intégration Accounto.
- **Portail participants/membres** : après Phase 2.
- **Phase 3** : dashboard, rappels automatisés, report builder, évaluations/questionnaires, tâches internes.

## Intégration Accounto (ERP/comptabilité)

- QR-factures suisses exclusivement, aucun PSP.
- Flux : Moléson pousse la facture → Accounto génère le PDF QR + référence → Moléson récupère le PDF (`GET /documents/{id}`) et l'envoie par email au participant → polling du statut de paiement (`GET /invoices` avec `updated_at_start`), pas de webhooks.
- `external_identifier` non inscriptible à la création → corrélation via `reference` + table de correspondance inscription ↔ invoice ID.
- L'envoi d'emails reste dans Moléson (Accounto n'envoie pas).

## Modèle métier clé

- **Code cours** : `AAAA-Px-NNNNNN[v]-RG` (année, période T4/S1/S2, identifiant à préfixe matière, variante optionnelle, région). Régions : FR Sarine/Fribourg-ville, GR Gruyère/Bulle, GL Glâne/Romont, SN Singine/Düdingen. La région est une entité de premier ordre (navigation du site).
- **Tarifs** : prix de base par cours ; rabais par type de membre : supporter 5%, actif 10%, bienfaiteur 15%, collaborateurs 10% — tous hors cours intensifs (flag `is_intensive` sur le cours neutralise les rabais). Pas de tarif AVS/jeunes. Surcharge manuelle possible par inscription (promos).
- **Reconduction** : workflow central — les inscriptions des fidèles sont reconduites de trimestre en trimestre puis confirmées (chez Welante : copie manuelle par le secrétariat, statut « Copié »). Moléson l'automatise : email « votre cours continue » + confirmation en un clic.
- **Contact de facturation** distinct possible sur une inscription (employeur, proche) — requis pour Accounto.
- **Sessions** : chaque séance porte sa propre date/heure/salle (les horaires varient au sein d'un même cours). Les documents (factures, confirmations) puisent dans les sessions.
- Taxonomie des cours (matières, hiérarchie à 2 niveaux, slugs = Web-Codes Welante à préserver) séparée des flags marketing (Newsletter, Highlight, démarrage garanti) et des types administratifs (ORS, formation interne, privés & entreprises).

## Authentification

- Magic links (email, sans mot de passe) pour participants/membres — envisager OTP plutôt que lien cliquable sur mobile (problèmes cross-browser).
- Passkeys/WebAuthn envisagés pour admin et formateurs.
- ~12 participants sans email : inscription assistée par le secrétariat, toujours possible.

## Données sensibles (nLPD)

- Les exports Welante (dossier `data/`, JAMAIS commité) contiennent numéros AVS, IBAN, données personnelles.
- No AVS des formateurs : chiffré au repos, accès restreint au rôle admin-comptabilité, exclu des exports par défaut.
- Ne jamais inclure de données personnelles réelles dans les tests, fixtures, seeds ou logs.

## Migration depuis Welante

- Sources : exports Excel dans `data/` (catégories, cours, intervenants, participants/inscriptions, membres) — voir `docs/analyse-exports-welante.md` pour les anomalies détaillées.
- Points d'attention : descriptifs DE+FR concaténés à découper (validation humaine), IBAN à normaliser, double en-tête dans membres.xlsx, colonne « Chiffre » = artefact à ignorer, notes historiques importées en archive lecture seule, mapping des anciennes catégories de membres à valider, anciens formats de codes cours à tolérer.

## Environnement & outils

- Docker / devcontainer pour la portabilité multi-machines (Olivier voyage). VPS prévu pour staging.
- PDF : pandoc + weasyprint (wkhtmltopdf abandonné, Unicode peu fiable).
- Documents de référence dans `docs/` : moleson-document-de-reference.pdf, correspondance-welante-moleson.md, analyse-exports-welante.md.
