"""Séparation des contenus bilingues concaténés par Welante.

Un découpage faux est pire qu'un découpage refusé : il passerait inaperçu
jusqu'à la publication du programme. Ces tests vérifient donc autant ce que le
découpeur accepte que ce qu'il envoie en relecture.

Tous les textes sont inventés.
"""

import pytest

from apps.welante.language import detect_language, split_bilingual

# --- Détection de langue ---------------------------------------------------


def test_une_phrase_francaise_est_reconnue():
    score = detect_language("Ce cours s'adresse aux personnes qui souhaitent progresser")

    assert score.language == "fr"
    assert score.is_certain


def test_une_phrase_allemande_est_reconnue():
    score = detect_language("Dieser Kurs richtet sich an alle, die mit uns lernen möchten")

    assert score.language == "de"
    assert score.is_certain


def test_les_lettres_propres_a_une_langue_sauvent_les_textes_courts():
    """« Anfänger » n'a pas de mot-outil, mais son ä ne ment pas."""
    assert detect_language("Anfänger").language == "de"
    assert detect_language("Débutant").language == "fr"


def test_un_texte_sans_indice_ne_pretend_pas_trancher():
    score = detect_language("Yoga Pilates 2026")

    assert score.confidence == 0.0
    assert not score.is_certain


def test_un_texte_vide_ne_lance_pas_d_erreur():
    assert detect_language("").confidence == 0.0
    assert detect_language("   ").confidence == 0.0


# --- Découpage sur séparateur explicite ------------------------------------


def test_un_titre_separe_par_une_barre_oblique_se_coupe():
    resultat = split_bilingual("Italienisch für Anfänger / Italien pour débutants")

    assert resultat.de == "Italienisch für Anfänger"
    assert resultat.fr == "Italien pour débutants"
    assert resultat.is_complete


def test_l_ordre_des_langues_est_deduit_et_non_suppose():
    """Welante concatène tantôt DE puis FR, tantôt l'inverse."""
    resultat = split_bilingual("Cours de cuisine pour tous / Kochkurs für alle")

    assert resultat.fr == "Cours de cuisine pour tous"
    assert resultat.de == "Kochkurs für alle"


def test_un_separateur_present_plusieurs_fois_n_est_pas_utilise():
    """« et / ou » dans les deux moitiés rendrait la coupure arbitraire."""
    texte = "Peinture / dessin pour adultes / Malen / Zeichnen für Erwachsene"

    resultat = split_bilingual(texte)

    assert resultat.strategy != "séparateur « / »"


# --- Découpage par bascule de langue ---------------------------------------


def test_un_descriptif_sur_deux_paragraphes_se_coupe():
    texte = (
        "Dieser Kurs richtet sich an alle, die mit uns die Grundlagen lernen möchten.\n"
        "Die Lektionen finden jede Woche statt.\n"
        "Ce cours s'adresse à toutes les personnes qui souhaitent apprendre les bases.\n"
        "Les séances ont lieu chaque semaine."
    )

    resultat = split_bilingual(texte)

    assert resultat.de.startswith("Dieser Kurs")
    assert resultat.fr.startswith("Ce cours")
    assert resultat.is_complete
    assert not resultat.needs_review


def test_l_ordre_inverse_est_aussi_reconnu():
    texte = (
        "Ce cours s'adresse à toutes les personnes qui souhaitent apprendre les bases.\n"
        "Les séances ont lieu chaque semaine dans nos locaux.\n"
        "Dieser Kurs richtet sich an alle, die mit uns die Grundlagen lernen möchten.\n"
        "Die Lektionen finden jede Woche statt."
    )

    resultat = split_bilingual(texte)

    assert resultat.fr.startswith("Ce cours")
    assert resultat.de.startswith("Dieser Kurs")


# --- Ce qui doit partir en relecture ---------------------------------------


def test_un_texte_monolingue_part_en_relecture_avec_l_autre_langue_vide():
    resultat = split_bilingual(
        "Ce cours s'adresse à toutes les personnes qui souhaitent progresser."
    )

    assert resultat.fr
    assert resultat.de == ""
    assert resultat.needs_review
    assert not resultat.is_complete


def test_un_titre_court_sans_indice_part_en_relecture():
    """« Aquagym Wassergymnastik » : deux mots, aucun indice grammatical."""
    resultat = split_bilingual("Aquagym Wassergymnastik")

    assert resultat.needs_review


def test_un_decoupage_peu_sur_est_signale_plutot_qu_impose():
    resultat = split_bilingual("Yoga 2026 / Pilates 2026")

    assert resultat.needs_review


def test_un_champ_vide_ne_demande_pas_de_relecture():
    resultat = split_bilingual("")

    assert (resultat.fr, resultat.de) == ("", "")
    assert not resultat.needs_review


@pytest.mark.parametrize("texte", ["", "   ", "\n\n"])
def test_les_champs_blancs_sont_traites_sans_erreur(texte):
    resultat = split_bilingual(texte)

    assert not resultat.needs_review


def test_le_decoupage_ne_perd_aucun_contenu():
    """Contrôle de non-perte : tout mot du texte d'origine doit se retrouver."""
    texte = "Kochkurs für alle Stufen / Cours de cuisine pour tous les niveaux"

    resultat = split_bilingual(texte)

    mots_origine = set(texte.replace("/", " ").split())
    mots_resultat = set((resultat.fr + " " + resultat.de).split())
    assert mots_origine == mots_resultat


def test_le_motif_de_relecture_distingue_langue_manquante_et_doute():
    """« À relire » recouvre deux situations très différentes : elles doivent se lire."""
    une_seule_langue = split_bilingual(
        "Ce cours s'adresse à toutes les personnes qui souhaitent progresser."
    )
    indetermine = split_bilingual("Aquagym Wassergymnastik")

    assert "Une seule langue détectée (français)" in une_seule_langue.review_reason
    # Le texte est rangé en français faute de mieux : le motif ne doit surtout pas
    # laisser croire que la langue a été reconnue.
    assert "Langue indéterminée" in indetermine.review_reason
    assert "détectée" not in indetermine.review_reason


def test_un_decoupage_sur_n_a_pas_de_motif_de_relecture():
    resultat = split_bilingual("Italienisch für Anfänger / Italien pour débutants")

    assert resultat.review_reason == ""


# --- Formes rencontrées dans l'export réel ---------------------------------


def test_un_titre_articule_par_des_tirets_se_coupe_au_bon_endroit():
    """Forme dominante des titres réels : le tiret sert à la fois de ponctuation
    interne et de frontière entre les deux langues.

    Couper au premier tiret venu séparerait « Deutsch A1 » de « Anfänger » ;
    ne pas couper du tout rangeait la moitié française en allemand — c'est ce
    qui se produisait, sur 232 champs, avant que l'export réel ne le révèle.
    """
    resultat = split_bilingual(
        "Deutsch A1 - Anfänger, los geht's! - Allemand A1 - Débutants, lancez-vous !"
    )

    assert resultat.de == "Deutsch A1 - Anfänger, los geht's!"
    assert resultat.fr == "Allemand A1 - Débutants, lancez-vous !"
    assert resultat.is_complete


def test_le_tiret_d_articulation_ne_reste_pas_en_bord_de_fragment():
    resultat = split_bilingual("Deutsch A2 - Was gibt's Neues? - Allemand A2 - Quoi de neuf ?")

    assert not resultat.fr.startswith("-")
    assert not resultat.de.endswith("-")


def test_un_titre_monolingue_a_tirets_n_est_pas_scinde_en_deux_langues():
    """« Deutsch B1 - Lass uns Deutsch sprechen! » n'a pas de version française.

    Inventer une traduction est plus grave que d'en signaler l'absence.
    """
    resultat = split_bilingual("Deutsch B1 - Lass uns Deutsch sprechen!")

    assert resultat.fr == ""
    assert resultat.de
    assert resultat.needs_review


def test_le_nom_de_la_langue_enseignee_sert_d_indice():
    """Dans « Allemand A1 », aucun mot grammatical : le nom de la matière tranche."""
    from apps.welante.language import detect_language

    assert detect_language("Allemand A1").language == "fr"
    assert detect_language("Deutsch A1").language == "de"
