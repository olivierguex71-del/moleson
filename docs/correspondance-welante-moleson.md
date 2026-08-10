# Table de correspondance Welante → Moléson

**Complément au document de référence Moléson** · Version 1.0 · 10.08.2026

Objectif : garantir la couverture fonctionnelle complète avant migration. Chaque élément du menu Welante est classé selon l'un des cinq statuts suivants :

| Statut | Signification |
|---|---|
| ✅ **Repris** | Fonctionnalité équivalente, modélisée de façon similaire |
| 🔀 **Fusionné** | Absorbé dans une entité ou un écran plus large de Moléson |
| ⬆️ **Amélioré** | Repris avec une refonte significative (modèle ou UX) |
| ⏳ **Reporté** | Prévu, mais dans une phase ultérieure |
| ❌ **Abandonné** | Volontairement non repris (poids mort ou remplacé par l'architecture) |

---

## 1. Résumé (dashboard)

| Élément Welante | Statut | Équivalent Moléson | Phase | Notes |
|---|---|---|---|---|
| Widget recherche contacts | ✅ Repris | Recherche globale (contacts, cours, factures) | 1 | Une seule barre de recherche transversale plutôt qu'un widget par module |
| Inscriptions par Internet (liste + statistiques) | ⬆️ Amélioré | File de validation des inscriptions web | 1 | Le site web consomme l'API publique ; les inscriptions arrivent nativement, pas via un canal externe importé |
| Rappel (tâches assignées) | ⏳ Reporté | Tâches / rappels internes assignables | 3 | Utile (assignation à un utilisateur, lien vers un cours, échéance) mais non bloquant. À distinguer des **rappels de paiement** (Phase 2) |
| Charger fichier QR (camt.054) | ❌ Abandonné | — | — | Rendu obsolète par l'intégration Accounto : le statut de paiement est synchronisé par polling. Argument commercial clé : plus aucun upload bancaire manuel |
| Paiements par QR / Comptabilité | 🔀 Fusionné | Module Facturation + Accounto | 2 | La comptabilité vit dans Accounto ; Moléson affiche le statut, il ne fait pas de compta |

## 2. Contacts

| Élément Welante | Statut | Équivalent Moléson | Phase | Notes |
|---|---|---|---|---|
| Liste | ✅ Repris | Entité **Contact** (CRUD) | 1 | Socle du module |
| Participant-e-s | 🔀 Fusionné | Rôle/vue sur Contact | 1 | Pas une entité séparée : un contact devient participant via ses inscriptions. Évite les doublons structurels de Welante |
| Groupes | ✅ Repris | Groupes de contacts (tags/segments) | 1 | Sert au ciblage des communications et aux tarifs de groupe éventuels |
| Notes | 🔀 Fusionné | Notes horodatées sur la fiche contact | 1 | En contexte sur la fiche, pas un écran séparé |
| Format de l'adresse | ❌ Abandonné | — | — | Symptôme d'une mauvaise modélisation : Moléson stocke l'adresse en champs structurés (norme suisse, compatible QR-facture) et le formatage est automatique |
| Doublons | ⬆️ Amélioré | Détection de doublons **à la saisie** | 1 | Suggestion en temps réel (nom/email/adresse proches) plutôt qu'un écran de nettoyage a posteriori. Écran de fusion conservé pour la migration CSV |

## 3. Cours

| Élément Welante | Statut | Équivalent Moléson | Phase | Notes |
|---|---|---|---|---|
| Liste | ✅ Repris | Entité **Cours** (CRUD, bilingue FR/DE natif) | 1 | Titre, description, contenu : chaque champ existe dans les deux langues |
| Jours de cours | 🔀 Fusionné | **Sessions** gérées dans la fiche cours | 1 | Plus d'écran séparé : les séances se créent/modifient en contexte, avec génération récurrente |
| Jours d'absence | 🔀 Fusionné | Exceptions de calendrier dans la fiche cours + jours fériés globaux | 1 | Deux niveaux : fériés cantonaux (FR) globaux + exceptions par cours |
| Intervenant-e-s | ✅ Repris | Entité **Formateur/Formatrice** | 1 | Liée au portail formateurs (post-Phase 1) : présences, listes imprimables |
| Lieux | ✅ Repris | Entité **Lieu** (partagée) | 1 | Référentiel unique, partagé avec les réservations si le module est retenu |
| Prix | ⬆️ Amélioré | Grille tarifaire par cours (standard, membre, réduit…) | 1 | Modélisé comme des catégories de prix rattachées au cours, sélectionnées à l'inscription |
| Types de cours | 🔀 Fusionné | Taxonomie unifiée du cours | 1 | Types + catégories + périodes = trois écrans Welante fusionnés en attributs gérés dans la fiche cours ; référentiels accessibles en second plan dans les paramètres |
| Catégories | 🔀 Fusionné | Taxonomie unifiée (cf. ci-dessus) | 1 | Bilingue, exposée dans l'API publique pour le filtrage sur le site web |
| Périodes | 🔀 Fusionné | Attribut période/semestre du cours | 1 | Utilisé pour la numérotation (ex. 2026-T4) et le filtrage |

## 4. Réservations

| Élément Welante | Statut | Équivalent Moléson | Phase | Notes |
|---|---|---|---|---|
| Liste | ⏳ Reporté (à confirmer) | Module Réservation de salles | 3 ou jamais | **Question ouverte : l'institution loue-t-elle réellement ses salles à des tiers ?** Si oui : module léger réutilisant les Lieux. Si non : abandonné |
| Lieux | 🔀 Fusionné | Référentiel Lieux commun | 1 | Pas de duplication cours/réservations comme chez Welante |
| Prix | ⏳ Reporté | Tarifs de location | 3 ou jamais | Suit la décision sur le module |

## 5. Calendrier

| Élément Welante | Statut | Équivalent Moléson | Phase | Notes |
|---|---|---|---|---|
| Calendrier global | ✅ Repris | Vue calendrier (cours, sessions, occupation des lieux) | 1 | Vue par lieu, par formateur, par période. Export iCal envisageable via l'API (abonnement calendrier pour les formateurs) |

## 6. Facturation

| Élément Welante | Statut | Équivalent Moléson | Phase | Notes |
|---|---|---|---|---|
| Liste | ⬆️ Amélioré | Entité **Facture** liée à Accounto | 2 | Moléson pousse les données → Accounto génère la QR-facture et la référence → Moléson récupère le PDF et l'envoie par email → polling du statut. Table de correspondance inscription ↔ invoice ID / `reference` |
| Crédits | ✅ Repris | Notes de crédit / avoirs | 2 | Nécessaire pour annulations et remboursements ; à valider côté API Accounto (Phase 0 étendue si besoin) |
| Articles | 🔀 Fusionné | Lignes de facturation dérivées des tarifs | 2 | Pas de catalogue d'articles séparé : les tarifs de cours génèrent les lignes ; articles libres possibles pour cas divers |
| Modes de paiement | ❌ Abandonné | — | — | Décision de principe : **QR-facture exclusivement**, pas de PSP. Un seul mode = pas d'écran de gestion |
| Rappel | ⬆️ Amélioré | Rappels de paiement automatisés | 2–3 | Base en Phase 2 (relance manuelle), automatisation (échéances, escalade) en Phase 3. Alimenté par le statut de paiement Accounto |

## 7. Évaluations

| Élément Welante | Statut | Équivalent Moléson | Phase | Notes |
|---|---|---|---|---|
| Liste / Questions / Réponses | ⏳ Reporté | Module questionnaires de satisfaction | 3 | Rattaché à un cours ou une session. Le modèle de données Phase 1 n'exige rien de particulier, seulement ne pas fermer la porte (clé étrangère vers cours/session) |

## 8. Paramètres

| Élément Welante | Statut | Équivalent Moléson | Phase | Notes |
|---|---|---|---|---|
| Utilisateurs | ⬆️ Amélioré | Utilisateurs + rôles + scopes API | 1 | Cœur du modèle API-first : admin, formateur, participant/membre, public. Magic links pour participants ; passkeys/WebAuthn envisagés pour admin et formateurs |
| Modèles PDF | 🔀 Fusionné | Centre **Modèles & communications** | 1–2 | Un seul centre pour tous les modèles, chaque modèle **existant en FR et DE d'office**. Génération PDF : pandoc + weasyprint |
| Modèles de courriels | 🔀 Fusionné | Centre Modèles & communications | 1–2 | Idem — confirmations d'inscription (Phase 1), envoi de factures (Phase 2), rappels (Phase 2–3) |
| Modèles Office | ❌ Abandonné | — | — | Les exports (listes de présence, etc.) sont générés directement (PDF/CSV/XLSX) depuis les données ; pas de dépendance à des modèles Word/Excel maintenus à la main |
| Modèles SMS | ⏳ Reporté | Canal SMS optionnel | 3 ou jamais | À confirmer : le SMS est-il réellement utilisé aujourd'hui ? Coût récurrent + intégration tierce. L'email couvre l'essentiel |
| Fichiers | ✅ Repris | Pièces jointes (cours, contacts, factures) | 1 | Stockage de documents rattachés aux entités |
| Facture (paramètres) | 🔀 Fusionné | Configuration Accounto + paramètres de facturation | 2 | Coordonnées de facturation, textes légaux bilingues, config API |
| Change | ❌ Abandonné | — | — | Taux de change : hors périmètre, tout est en CHF |
| Sources d'inscriptions | ⬆️ Amélioré | Attribut `source` sur l'inscription | 1 | Trivial dans un modèle API-first : chaque consommateur (admin, site web, portail) est identifié par son scope. Statistiques par source gratuites en Phase 3 |

---

## Synthèse

**Points d'attention issus de cette analyse :**

1. **Réservations** — décision à prendre : usage réel chez l'institution ? (conditionne un module entier)
2. **SMS** — décision à prendre : canal réellement utilisé ? (coût récurrent)
3. **Crédits/avoirs** — vérifier le support des notes de crédit dans l'API Accounto (à ajouter au périmètre de la Phase 0 si les annulations avec remboursement sont fréquentes)
4. **Tâches internes (Rappel du dashboard)** — confirmé utilisé activement (captures : tâches assignées avec échéances) → à ne pas oublier en Phase 3
5. **Export iCal** — opportunité à faible coût offerte par l'API, absente de Welante

**Bilan de couverture :** aucun écran Welante ne reste sans réponse. Les abandons (camt.054, modes de paiement, format d'adresse, change, modèles Office) sont tous justifiés par l'architecture — pas des pertes fonctionnelles, mais des symptômes de Welante rendus inutiles.
