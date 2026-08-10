"""Calcul du prix d'une inscription.

Isolé des modèles parce que c'est la règle métier la plus scrutée du projet :
elle doit se lire d'un trait, se tester sans base de données, et produire un
détail explicable — le secrétariat doit pouvoir dire à un participant *pourquoi*
il paie ce montant.

Ordre de résolution, du plus explicite au plus automatique :

1. **prix imposé** — un montant saisi à la main sur l'inscription remplace tout ;
2. **rabais accordé manuellement** — décision du secrétariat, elle prime y compris
   sur un cours intensif : refuser tout geste commercial sur un intensif serait
   une règle que personne n'a demandée ;
3. **cours intensif** — neutralise les rabais automatiques (adhésion, collaborateur) ;
4. **rabais du contact** — le plus avantageux de ses droits, jamais cumulé.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.utils.translation import gettext_lazy as _

#: Les montants sont en francs, au centime. La QR-facture accepte le centime ;
#: si l'Unipop souhaite l'arrondi commercial à 5 centimes, c'est ici que la
#: décision se pose — et nulle part ailleurs.
CENTIME = Decimal("0.01")


@dataclass(frozen=True)
class PriceBreakdown:
    """Détail d'un prix : ce qu'on facture, et pourquoi."""

    base_price: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    final_price: Decimal
    explanation: str

    @property
    def has_discount(self) -> bool:
        return self.discount_amount > 0


def _arrondi(montant: Decimal) -> Decimal:
    return montant.quantize(CENTIME, rounding=ROUND_HALF_UP)


def compute_price(
    *,
    base_price: Decimal,
    is_intensive: bool = False,
    contact_discount_percent: Decimal = Decimal("0"),
    contact_discount_label: str = "",
    price_override: Decimal | None = None,
    discount_override: Decimal | None = None,
) -> PriceBreakdown:
    """Calcule le prix effectif d'une inscription et son détail."""
    base_price = _arrondi(Decimal(base_price))

    if price_override is not None:
        impose = _arrondi(Decimal(price_override))
        return PriceBreakdown(
            base_price=base_price,
            discount_percent=Decimal("0"),
            discount_amount=_arrondi(base_price - impose),
            final_price=impose,
            explanation=str(_("Prix imposé sur l'inscription")),
        )

    if discount_override is not None:
        pourcentage = Decimal(discount_override)
        explication = str(_("Rabais accordé manuellement"))
    elif is_intensive:
        pourcentage = Decimal("0")
        explication = str(_("Cours intensif : aucun rabais applicable"))
    else:
        pourcentage = Decimal(contact_discount_percent)
        explication = contact_discount_label or str(_("Tarif plein"))

    pourcentage = max(Decimal("0"), min(pourcentage, Decimal("100")))
    remise = _arrondi(base_price * pourcentage / Decimal("100"))

    return PriceBreakdown(
        base_price=base_price,
        discount_percent=pourcentage,
        discount_amount=remise,
        final_price=_arrondi(base_price - remise),
        explanation=explication,
    )
