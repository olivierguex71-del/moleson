"""Le socle bilingue : deux colonnes par contenu, jamais de concaténation."""

import pytest
from django.utils.translation import override

from apps.core.models import TranslatedFieldsMixin, content_language


class CoursFactice(TranslatedFieldsMixin):
    """Objet minimal portant des champs bilingues, sans passer par la base."""

    def __init__(self, title_fr="", title_de="", summary_fr="", summary_de=""):
        self.title_fr = title_fr
        self.title_de = title_de
        self.summary_fr = summary_fr
        self.summary_de = summary_de


@pytest.mark.parametrize(
    ("demandee", "attendue"),
    [
        ("fr", "fr"),
        ("de", "de"),
        ("de-ch", "de"),
        ("FR", "fr"),
        ("it", "fr"),  # l'italien n'est pas une langue de contenu : repli
        (None, "fr"),
    ],
)
def test_normalisation_de_la_langue(demandee, attendue):
    assert content_language(demandee) == attendue


def test_lecture_dans_chaque_langue():
    cours = CoursFactice(title_fr="Italien débutant", title_de="Italienisch Anfänger")

    assert cours.tr("title", "fr") == "Italien débutant"
    assert cours.tr("title", "de") == "Italienisch Anfänger"


def test_la_langue_active_est_utilisee_par_defaut():
    cours = CoursFactice(title_fr="Aquagym", title_de="Wassergymnastik")

    with override("de"):
        assert cours.tr("title") == "Wassergymnastik"
    with override("fr"):
        assert cours.tr("title") == "Aquagym"


def test_repli_sur_l_autre_langue_si_la_traduction_manque():
    """Mieux vaut afficher l'allemand qu'un titre vide sur une page française."""
    cours = CoursFactice(title_fr="", title_de="Nur auf Deutsch")

    assert cours.tr("title", "fr") == "Nur auf Deutsch"


def test_repli_desactivable_pour_detecter_les_manques():
    cours = CoursFactice(title_fr="", title_de="Nur auf Deutsch")

    assert cours.tr("title", "fr", fallback=False) == ""


def test_liste_des_traductions_manquantes():
    cours = CoursFactice(title_fr="Anglais A1", title_de="Englisch A1", summary_fr="   ")

    assert cours.missing_translations("title", "summary") == ["summary_fr", "summary_de"]


def test_aucune_traduction_manquante_quand_tout_est_rempli():
    cours = CoursFactice(
        title_fr="Anglais A1",
        title_de="Englisch A1",
        summary_fr="Cours du soir",
        summary_de="Abendkurs",
    )

    assert cours.missing_translations("title", "summary") == []
