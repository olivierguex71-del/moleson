# Analyse des exports Welante — validation du schéma Moléson

Version 1.0 · 10.08.2026 · Basé sur : Catégories (42), Cours (15), Intervenant-e-s (107), Participant-e-s (349 inscriptions), Membres (125), 1 facture PDF (184008)

---

## 1. Convention de numérotation des cours (déchiffrée)

Format : `AAAA-Px-NNNNNN[v]-RG`

| Segment | Signification | Exemples |
|---|---|---|
| `AAAA` | Année | 2026 |
| `Px` | Période (trimestre/semestre) | T4, S1, S2 |
| `NNNNNN` | Identifiant, préfixe = matière | 44xxxx anglais, 42xxxx italien, 72xxxx aquatique, 73xxxx santé, 02/06xxxx société |
| `[v]` | Variante optionnelle | `421111b` (facture 184008) |
| `RG` | **Région** | FR Sarine/Fribourg-ville, GR Gruyère (Bulle), GL Glâne (Romont), SN Singine (Düdingen) |

⚠️ Le suffixe est la région, pas la langue. Ancien format pré-2023 visible dans les notes : `1617-272-318`, `2021-72-1021-SN` — la migration de l'historique devra tolérer plusieurs formats.

✅ **Résolu — colonne "Chiffre"** : artefact d'export bugué de Welante. La colonne contient simplement la dernière lettre du suffixe régional (FR→R, GL→L, SN→N), résultat d'un mauvais découpage du code. **À ignorer totalement à la migration** ; la région se parse depuis le suffixe complet du code cours.

## 2. Modèle tarifaire (définitif)

- Prix de base par cours : 150–478 CHF observés.
- **Rabais par type de membre, en pourcentage du prix de base** :

| Type de membre | Rabais | Exclusion |
|---|---|---|
| Membre supporter | 5% | hors cours intensifs |
| Membre actif | 10% | hors cours intensifs |
| Membre bienfaiteur | 15% | hors cours intensifs |
| Collaborateur/trice | 10% | hors cours intensifs |

- Pas de tarif AVS/jeunes (confirmé).
- Promos ponctuelles observées dans les notes ("réduction immédiate de 5%") → champ rabais/promo supplémentaire par inscription.
- Facilités de paiement mentionnées sur le site pour les cours > 3 mois → échéancier possible (Phase 2+, à confirmer avec Accounto).

**Schéma Moléson** : table `membership_type` (supporter, actif, bienfaiteur) avec `discount_percent` ; les collaborateurs sont un rôle, pas un type de membre, avec leur propre rabais de 10%. Chaque cours porte un flag `is_intensive` qui neutralise tous les rabais. Le prix effectif = prix de base × (1 − rabais applicable), surcharge manuelle possible par inscription (promos, cas particuliers).

⚠️ **Correspondance à valider à la migration** : les exports Welante montrent les catégories `Supporter-Mitglied`, `Mitarbeiter`, `Vorstandsmitglied` — mais pas de trace distincte des membres « actifs » et « bienfaiteurs ». Mapping à confirmer (Vorstandsmitglied → membre actif ? bienfaiteur ?), et vérifier comment les cours intensifs sont identifiés dans Welante (aucune catégorie « intensif » dans l'export des catégories — flag interne ? convention de nommage ?).

## 3. Anomalies et découvertes par fichier

### Cours (15 lignes, échantillon)
| Constat | Impact migration | Impact schéma |
|---|---|---|
| **Titre et Descriptif = DE+FR concaténés dans un seul champ** | Découpage automatique DE/FR + validation humaine | Confirme le bilinguisme par champ (`title_fr`, `title_de`…) |
| Catégories multiples séparées par `;` avec hiérarchie `Parent > Enfant` | Parsing du séparateur | Relation N-N cours↔catégories |
| "Newsletter", "Highlight", "Cours à démarrage garanti", "sur demande" mélangés aux catégories | Extraction vers des **flags** | Séparer taxonomie (matières) et étiquettes marketing/statut |
| Colonne "Femme" (0%/100%) et "Âge" | Ne pas migrer comme attributs du cours | ✅ Résolu : **statistiques** dérivées des inscriptions — Moléson les calcule à la volée (dashboard Phase 3), pas de stockage |
| "Lieu" contient parfois un nom de personne ("Favre Genilloud Catherine") | Nettoyage | Lieu = entité propre ; cours chez un particulier = adresse ad hoc |
| TN Min-Max ("5 - 8") en texte | Split en 2 entiers | `min_participants`, `max_participants` |
| Horaires hétérogènes (facture : "2x mardi 15:45, 4x jeudi 16:00, 1x mardi 16:00") | — | Les **sessions individuelles** portent chacune date+heure+salle ; pas d'horaire unique au niveau cours |

### Participant-e-s (349 inscriptions)
| Constat | Impact |
|---|---|
| Statut unique "Copié" → **workflow de réinscription par copie** trimestre → trimestre, puis confirmation | Fonctionnalité clé à modéliser : reconduction avec statut (proposée → confirmée/déclinée). Candidat idéal à l'automatisation par magic link |
| 28 contacts en doublon dans le fichier | Normal (1 ligne = 1 inscription) — confirme la séparation contact / inscription |
| **12 inscriptions sans email** | ⚠️ Magic link impossible pour ces personnes → prévoir gestion par le secrétariat (inscription assistée) |
| 8 cas de **contact de facturation distinct** (ex. employeur, proche) | Relation `billing_contact` optionnelle sur l'inscription — requis aussi pour Accounto |
| Coquilles d'adresses ("Villars -sur-Glâne") | Normalisation NPA/localité à la migration (référentiel des NPA suisses) |
| Dates "Créé" en serial Excel dans l'export brut | Conversion gérée par pandas ; vigilance sur les autres exports |

### Membres (125 lignes)
| Constat | Impact |
|---|---|
| **Double ligne d'en-tête** (ligne 2 = sous-en-têtes partiels "Mitglieder", "Funktion"…) | Script d'import : `skiprows` ciblé |
| Types : supporter (~122), comité/Vorstand (2-3), collaborateurs (2-3) | Table `membership` avec type + période de validité |
| Colonnes "Programmversand Herbst 2019/Frühling 2020/…" ajoutées **par saison** | Anti-pattern Welante : une colonne par campagne. Moléson : table `mailing_campaign` + envois |
| Champ Notes = **journal d'audit de 10 ans en texte concaténé** (copies, Covid, remboursements, échanges) | Import en note d'archive lecture seule ; Moléson tient une vraie table d'événements horodatés |
| Langue : 77 FR / 45 DE | Confirme : chaque contact a une langue de correspondance, toutes les communications doivent exister en FR et DE |
| Formule d'appel stockée en texte ("Sehr geehrte Frau X") | Générée automatiquement depuis genre+langue+nom dans Moléson |

### Intervenant-e-s (107 lignes)
| Constat | Impact |
|---|---|
| IBAN : 66 avec espaces, 22 sans, 19 absents | Normalisation + validation (checksum IBAN) à la migration |
| Champ "Bank IBANname" mélange noms de banque et codes BIC ("Postfinance", "POFICHBEXXX", "banque Migros") | Champs séparés `bank_name` / `bic` (le BIC est dérivable de l'IBAN CH) |
| **No AVS présents** (756.xxxx) | 🔒 Donnée sensible nLPD : chiffrement au repos, accès restreint au rôle admin-comptabilité, exclue des exports par défaut |
| 98/107 emails en @unipopfr.ch | Alias institutionnels — prévoir email privé + email institutionnel ? ❓ à clarifier |
| ~15 colonnes de questionnaire FIDE polluent le schéma contact ("Pourquoi faites-vous le test fide ?"…) | Anti-pattern : champs de formulaire devenus colonnes de contact. Moléson : les réponses de questionnaire restent liées au questionnaire (cf. module Évaluations Phase 3) |
| Renonciation AVS : 2 cas | Champ booléen sur le profil formateur (paie) |

### Catégories (42 lignes)
- Hiérarchie à 2 niveaux (Cours de langues > 13 langues ; Compétences de base > 3 ; Sports & Loisirs > 3 ; ORS > 2).
- `Web-Code` = identifiant public stable → conserver comme slug à la migration (continuité des URL du site).
- Coquille dans les données sources : "Informatique & Technonolgie" → corriger à l'import.
- À séparer en 3 concepts : **taxonomie** (matières), **flags marketing** (Newsletter, Highlight, démarrage garanti, sur demande), **types administratifs** (Formation interne, Cours privés & entreprises, ORS).

### Facture 184008 (PDF)
- Document combiné **confirmation + facture** : bon pattern, à conserver dans le modèle Accounto.
- QR-IBAN : CH21 3000 0001 1700 4851 9 ; référence structurée QRR (`00 00000 00016 65740 00018 40088`) — à faire générer par Accounto et à corréler via `reference`.
- Délai de paiement : 10 jours.
- Contenu riche : professeur, dates détaillées de chaque séance, salles multiples → la génération de facture doit puiser dans les sessions, pas seulement le cours.
- Émetteur : "Université populaire du Canton de Fribourg - Volkshochschule" — dénomination bilingue partout.

## 4. Décisions & questions ouvertes

1. ~~Signification du "Chiffre" R/L/N~~ ✅ Résolu : artefact d'export (dernière lettre du suffixe régional, mal découpée par Welante) → colonne ignorée à la migration
2. ~~Colonnes "Femme"/"Âge"~~ ✅ Résolu : **statistiques** (pas des contraintes d'admission) → calculées à la volée depuis les inscriptions, non stockées sur le cours
3. ~~Emails @unipopfr.ch des formateurs~~ ✅ Résolu : pas d'email privé supplémentaire à stocker à ce stade — un seul champ email suffit
4. ~~Rabais membres~~ ✅ Résolu : 5% supporter / 10% actif / 15% bienfaiteur / 10% collaborateurs, tous **hors cours intensifs** (cf. section 2). Reste à valider : mapping des anciennes catégories Welante et identification des cours intensifs dans les données sources
5. **12 participants sans email** : politique à définir (téléphone ? courrier ? gestion 100% secrétariat ?)
6. **Reconduction automatisée** : la copie trimestrielle manuelle peut devenir un email automatique « votre cours continue, confirmez en un clic » (magic link) — gain de temps majeur pour le secrétariat. À valider comme fonctionnalité du portail participant.

## 5. Prochaines étapes concrètes

1. Schéma SQL complet intégrant ces constats (contacts, membership, cours bilingues, sessions, catégories vs flags, price_categories, inscriptions avec billing_contact et reconduction, formateurs avec données paie chiffrées).
2. Scripts de migration Python (pandas) : un par export, avec normalisation (IBAN, NPA, dates), découpage DE/FR des descriptifs, rapport d'anomalies par ligne.
3. Passe de validation : liste des lignes nécessitant un arbitrage humain (découpages DE/FR douteux, adresses invalides, emails manquants).
