"""Résolution des colonnes d'un export.

Le point critique n'est pas de trouver une colonne plausible, mais de trouver
**toujours la même**, et la bonne.
"""

from apps.welante.columns import Column, normalize_header, resolve_columns


def test_les_intitules_sont_compares_sans_accent_ni_casse():
    assert normalize_header("Catégorie") == normalize_header("CATEGORIE")
    assert normalize_header("TN Min - Max") == "tn_min_max"
    assert normalize_header("Formateur/trice AHV-Nr.") == "formateur_trice_ahv_nr"


def test_l_ordre_des_alias_fixe_la_priorite():
    """Cas réel : « Formateur/trice Bank IBANname » est renseignée à 60 %,
    « Banque » à 1 %. Les deux existent dans le même export ; c'est l'ordre
    déclaré qui doit trancher, pas le hasard.
    """
    colonne = Column("bank", ("Formateur/trice Bank IBANname", "Banque"))

    mapping = resolve_columns(["Banque", "Formateur/trice Bank IBANname"], [colonne])

    assert mapping.get("bank") == "Formateur/trice Bank IBANname"


def test_la_resolution_est_stable_d_une_execution_a_l_autre():
    """Un ensemble non ordonné ferait varier le résultat entre deux processus,
    le hachage des chaînes étant randomisé par Python.
    """
    colonne = Column("ahv_number", ("Formateur/trice AHV-Nr.", "No AVS", "No d'AVS"))

    assert colonne.candidates == ("ahv_number", "formateur_trice_ahv_nr", "no_avs", "no_d_avs")


def test_un_alias_de_repli_sert_quand_le_prefere_est_absent():
    colonne = Column("bank", ("Formateur/trice Bank IBANname", "Banque"))

    mapping = resolve_columns(["Banque"], [colonne])

    assert mapping.get("bank") == "Banque"


def test_une_colonne_absente_est_signalee_sans_faire_echouer():
    colonnes = [Column("code", required=True), Column("notes")]

    mapping = resolve_columns(["Code"], colonnes)

    assert mapping.get("code") == "Code"
    assert [c.name for c in mapping.missing] == ["notes"]
    assert mapping.missing_required == []


def test_les_colonnes_inattendues_sont_listees():
    mapping = resolve_columns(["Code", "Colonne exotique"], [Column("code")])

    assert mapping.unexpected == ["Colonne exotique"]


def test_un_export_est_trouve_quelle_que_soit_la_casse_de_son_nom(tmp_path):
    """Le nom d'un fichier téléchargé dépend de la langue d'interface de Welante
    et du navigateur : « Categories.xlsx », « categories.xlsx », « Kategorien »…
    """
    import pandas as pd

    from apps.welante.sources import find_sources

    pd.DataFrame([{"Catégorie": "Cours de langues"}]).to_excel(
        tmp_path / "categories_2026.xlsx", index=False
    )

    trouve = {f.source.key: f for f in find_sources(tmp_path)}["categories"]

    assert trouve.exists
    assert trouve.path.name == "categories_2026.xlsx"


def test_les_fichiers_temporaires_d_excel_sont_ignores(tmp_path):
    """Excel laisse des « ~$fichier.xlsx » ouverts, illisibles et sans données."""
    import pandas as pd

    from apps.welante.sources import find_sources

    pd.DataFrame([{"Catégorie": "Cours de langues"}]).to_excel(
        tmp_path / "Categories.xlsx", index=False
    )
    (tmp_path / "~$Categories.xlsx").write_bytes(b"verrou Excel")

    trouve = {f.source.key: f for f in find_sources(tmp_path)}["categories"]

    assert trouve.path.name == "Categories.xlsx"
