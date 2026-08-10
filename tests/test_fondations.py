"""Vérifie que les choix de la stack tiennent réellement, pas seulement sur le papier."""

import pytest
from django.conf import settings
from django.db import connection


@pytest.mark.django_db
def test_les_extensions_postgres_sont_installees():
    with connection.cursor() as cursor:
        cursor.execute("SELECT extname FROM pg_extension")
        extensions = {ligne[0] for ligne in cursor.fetchall()}

    assert {"unaccent", "pg_trgm"} <= extensions


@pytest.mark.django_db
def test_la_recherche_ignore_les_accents():
    """« Glâne » doit se trouver en tapant « Glane », « Düdingen » en tapant « Dudingen »."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT unaccent('Glâne'), unaccent('Düdingen')")
        glane, dudingen = cursor.fetchone()

    assert glane == "Glane"
    assert dudingen == "Dudingen"


@pytest.mark.django_db
def test_la_similarite_par_trigrammes_detecte_les_quasi_doublons():
    """Socle de la détection de doublons à la saisie d'un contact."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT similarity('Villars-sur-Glâne', 'Villars -sur-Glane')")
        (score,) = cursor.fetchone()

    assert score > 0.5


def test_les_deux_langues_de_contenu_sont_declarees():
    assert settings.CONTENT_LANGUAGES == ("fr", "de")
    assert [code for code, _ in settings.LANGUAGES] == ["fr", "de"]
    assert settings.LANGUAGE_CODE == "fr"


def test_le_fuseau_horaire_est_suisse():
    assert settings.TIME_ZONE == "Europe/Zurich"
    assert settings.USE_TZ is True


def test_weasyprint_rend_un_pdf_avec_des_accents():
    """wkhtmltopdf a été abandonné pour son Unicode peu fiable : on le vérifie ici."""
    from weasyprint import HTML

    html = "<h1>Confirmation d'inscription — Bestätigung</h1><p>Glâne · Düdingen</p>"
    pdf = HTML(string=html).write_pdf()

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


@pytest.mark.django_db
def test_l_administration_exige_une_authentification(client):
    response = client.get("/admin/")

    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


@pytest.mark.django_db
def test_l_administration_repond_au_secretariat(staff_client):
    response = staff_client.get("/admin/")

    assert response.status_code == 200
    assert b"Mol" in response.content
