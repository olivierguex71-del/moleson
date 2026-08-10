# Transition vers Claude Code — kit de démarrage Moléson

## 1. Installer Claude Code (sur chaque machine)

macOS / Linux, dans le Terminal :

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Vérifier : `claude --version` (affiche un numéro de version suivi de « Claude Code »).

Premier lancement : taper `claude` — connexion dans le navigateur avec ton compte Claude existant (abonnement Pro/Max/Team/Enterprise ou compte Console requis). Les crédences sont stockées sur la machine ; à refaire une fois par machine.

Documentation officielle : https://code.claude.com/docs/en/quickstart

## 2. Créer le repo

```bash
# Sur GitHub/GitLab : créer un dépôt privé « moleson », puis :
git clone <url-du-repo> moleson
cd moleson
mkdir -p docs data
```

Y déposer :
- `CLAUDE.md` (fourni dans ce kit) → à la **racine** du repo
- `docs/` → moleson-document-de-reference.pdf, correspondance-welante-moleson.md, analyse-exports-welante.md
- `data/` → les 5 exports Excel + la facture PDF exemple

## 3. .gitignore AVANT le premier commit (critique — nLPD)

Les exports contiennent des numéros AVS, IBAN et données personnelles. Créer `.gitignore` à la racine :

```
# Données personnelles — ne JAMAIS commiter (nLPD)
data/
*.xlsx
*.xls
*_Facture_*.pdf

# Environnement
.env
.env.*
node_modules/
__pycache__/
*.pyc
.DS_Store
```

Puis seulement :

```bash
git add .
git status   # VÉRIFIER que data/ n'apparaît pas
git commit -m "Init: docs de référence et CLAUDE.md"
git push
```

Le dossier `data/` se recopie manuellement sur chaque machine (clé USB, cloud privé) — il ne transite jamais par GitHub.

## 4. Première session

```bash
cd moleson
claude
```

Commandes utiles dans la session : `/help` (aide), `/init` (analyse du repo — inutile ici, le CLAUDE.md est déjà fourni), `/resume` (reprendre une conversation précédente), Échap pour interrompre Claude en cours d'action.

Fonctionnement : tu écris en langage naturel (français ok). Claude Code montre ce qu'il compte faire avant chaque modification nécessitant une permission — tu approuves ou refuses à chaque étape. Au début, lis tout ; la confiance se construit.

## 5. Prompt de démarrage suggéré (à coller tel quel)

> Lis CLAUDE.md, docs/correspondance-welante-moleson.md et docs/analyse-exports-welante.md. Ensuite propose-moi un choix de stack technique (framework backend, base de données, frontend admin) adapté au projet et à un déploiement simple sur VPS, avec tes recommandations argumentées. Ne code rien avant qu'on ait validé la stack ensemble.

Puis, une fois la stack validée, sessions suivantes dans cet ordre :

1. **Session « fondations »** : devcontainer + docker-compose + structure du projet + CI minimale.
2. **Session « schéma »** : schéma SQL complet + migrations, basé sur l'analyse des exports.
3. **Session « migration »** : scripts d'import des exports `data/` avec rapport d'anomalies (découpage DE/FR, normalisation IBAN/NPA…).
4. **Session « Phase 0 »** : script de validation Accounto (nécessite tes credentials staging, en variables d'environnement `.env`, jamais commitées).
5. Puis Phase 1, entité par entité.

## 6. Rythme de travail multi-machines

- Fin de session : `git push` (ou demande à Claude Code de commiter et pousser).
- Autre machine : `git pull`, recopier `data/` si besoin, `claude`, et reprendre.
- Le CLAUDE.md garantit que chaque session — sur n'importe quelle machine — démarre avec tout le contexte du projet.

## 7. Réflexes de sécurité

- Toujours relire les commandes que Claude Code propose d'exécuter (surtout `rm`, opérations git destructives, envois réseau).
- Les secrets (Accounto, SMTP, base de données) vivent dans `.env`, jamais dans le code ni le CLAUDE.md.
- Vérifier périodiquement `git status` : aucun fichier de `data/` ne doit jamais être suivi.
