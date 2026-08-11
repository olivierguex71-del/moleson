"""Coquilles connues des données sources.

Partagées entre l'import des catégories et le rattachement des cours : corriger
un intitulé d'un côté seulement le rendrait introuvable de l'autre, et les cours
perdraient leur matière sans que rien ne paraisse fautif.
"""

#: Intitulé source → intitulé corrigé.
COQUILLES = {
    "informatique & technonolgie": "Informatique & Technologie",
    "informatique & technonolgie, tic": "Informatique & Technologie, TIC",
}


def corriger_intitule(nom: str) -> str:
    """Corrige un intitulé s'il figure parmi les coquilles connues."""
    return COQUILLES.get((nom or "").strip().lower(), nom)


def est_corrige(nom: str) -> bool:
    return corriger_intitule(nom) != nom
