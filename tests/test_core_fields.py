"""Le champ chiffré protège les données sensibles (No AVS des formateurs)."""

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import FieldError, ImproperlyConfigured

from apps.core.fields import EncryptedTextField

# Numéro AVS de forme valide mais entièrement inventé.
NUMERO_AVS_FICTIF = "756.0000.0000.00"


@pytest.fixture
def champ() -> EncryptedTextField:
    return EncryptedTextField(name="ahv_number")


def test_la_valeur_stockee_est_illisible(champ):
    stockee = champ.get_prep_value(NUMERO_AVS_FICTIF)

    assert stockee != NUMERO_AVS_FICTIF
    assert NUMERO_AVS_FICTIF not in stockee


def test_aller_retour_restitue_la_valeur(champ):
    stockee = champ.get_prep_value(NUMERO_AVS_FICTIF)

    assert champ.from_db_value(stockee, None, None) == NUMERO_AVS_FICTIF


def test_deux_ecritures_donnent_deux_chiffres_differents(champ):
    """Ce qui interdit les lookups — et rend l'analyse de fréquence inopérante."""
    assert champ.get_prep_value(NUMERO_AVS_FICTIF) != champ.get_prep_value(NUMERO_AVS_FICTIF)


@pytest.mark.parametrize("vide", [None, ""])
def test_les_valeurs_vides_traversent_sans_chiffrement(champ, vide):
    assert champ.get_prep_value(vide) == vide
    assert champ.from_db_value(vide, None, None) == vide


def test_rotation_de_cle(champ, settings, encryption_keys):
    """Une valeur chiffrée avec l'ancienne clé reste lisible après rotation."""
    ancienne, nouvelle = encryption_keys
    settings.MOLESON_ENCRYPTION_KEYS = [ancienne]
    historique = champ.get_prep_value(NUMERO_AVS_FICTIF)

    # La nouvelle clé passe en tête ; l'ancienne reste pour le déchiffrement.
    settings.MOLESON_ENCRYPTION_KEYS = [nouvelle, ancienne]

    assert champ.from_db_value(historique, None, None) == NUMERO_AVS_FICTIF
    assert champ.from_db_value(champ.get_prep_value("nouveau"), None, None) == "nouveau"


def test_cle_retiree_echoue_bruyamment(champ, settings):
    """Mieux vaut une erreur explicite qu'un No AVS silencieusement corrompu."""
    settings.MOLESON_ENCRYPTION_KEYS = [Fernet.generate_key().decode()]
    historique = champ.get_prep_value(NUMERO_AVS_FICTIF)
    settings.MOLESON_ENCRYPTION_KEYS = [Fernet.generate_key().decode()]

    with pytest.raises(ValueError, match="MOLESON_ENCRYPTION_KEYS"):
        champ.from_db_value(historique, None, None)


def test_absence_de_cle_est_une_erreur_de_configuration(champ, settings):
    settings.MOLESON_ENCRYPTION_KEYS = []

    with pytest.raises(ImproperlyConfigured, match="MOLESON_ENCRYPTION_KEYS"):
        champ.get_prep_value(NUMERO_AVS_FICTIF)


def test_le_champ_refuse_les_recherches(champ):
    """Un filtre sur un champ chiffré ne remonterait jamais rien : on le dit."""
    with pytest.raises(FieldError, match="pas interrogeable"):
        champ.get_lookup("exact")

    with pytest.raises(FieldError, match="pas interrogeable"):
        champ.get_lookup("icontains")


def test_le_champ_autorise_isnull(champ):
    """`isnull` porte sur la présence de la donnée, pas sur son contenu."""
    assert champ.get_lookup("isnull") is not None
