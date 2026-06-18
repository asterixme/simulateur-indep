"""
tax.py — Calcul de l'impôt sur le revenu (IR) et de l'impôt sur les sociétés (IS)
Barèmes 2026
"""

import json
from pathlib import Path


def _charger_config() -> dict:
    chemin = Path(__file__).parent.parent / "data" / "config.json"
    with open(chemin, "r", encoding="utf-8") as f:
        return json.load(f)


CONFIG = _charger_config()


def calculer_ir(revenu_imposable: float, nb_parts: float = 1.0) -> dict:
    """
    Calcule l'impôt sur le revenu selon le barème progressif 2026.

    Args:
        revenu_imposable: revenu net imposable annuel (€)
        nb_parts: quotient familial (1.0 = célibataire, 2.0 = marié sans enfant, etc.)

    Returns:
        dict avec montant_ir, taux_moyen, tmi (taux marginal d'imposition)
    """
    tranches = CONFIG["impot_revenu"]["tranches"]

    # Calcul sur le quotient familial
    revenu_par_part = revenu_imposable / nb_parts

    impot_par_part = 0.0
    tmi = 0.0
    borne_precedente = 0.0

    for tranche in tranches:
        borne = tranche["jusqu_a"]
        taux = tranche["taux"]

        if borne is None:
            # Dernière tranche : pas de plafond
            if revenu_par_part > borne_precedente:
                impot_par_part += (revenu_par_part - borne_precedente) * taux
                tmi = taux
            break
        else:
            if revenu_par_part <= borne_precedente:
                break
            montant_dans_tranche = min(revenu_par_part, borne) - borne_precedente
            impot_par_part += montant_dans_tranche * taux
            tmi = taux
            borne_precedente = borne

    montant_ir = impot_par_part * nb_parts
    taux_moyen = (montant_ir / revenu_imposable * 100) if revenu_imposable > 0 else 0

    return {
        "montant_ir": round(montant_ir, 2),
        "taux_moyen": round(taux_moyen, 2),
        "tmi": round(tmi * 100, 1),
        "revenu_imposable": round(revenu_imposable, 2),
        "nb_parts": nb_parts,
    }


def calculer_is(benefice: float) -> dict:
    """
    Calcule l'impôt sur les sociétés 2026.
    Taux réduit 15% jusqu'à 42 500€, puis 25% au-delà.
    (On suppose ici que les conditions du taux réduit sont remplies)

    Args:
        benefice: bénéfice imposable de la société (après rémunération dirigeant)

    Returns:
        dict avec montant_is, taux_effectif, detail
    """
    if benefice <= 0:
        return {"montant_is": 0, "taux_effectif": 0, "detail": {"part_taux_reduit": 0, "part_taux_normal": 0}}

    seuil = CONFIG["impot_societes"]["seuil_taux_reduit"]
    taux_reduit = CONFIG["impot_societes"]["taux_reduit"]
    taux_normal = CONFIG["impot_societes"]["taux_normal"]

    part_taux_reduit = min(benefice, seuil)
    part_taux_normal = max(0, benefice - seuil)

    is_reduit = part_taux_reduit * taux_reduit
    is_normal = part_taux_normal * taux_normal
    montant_is = is_reduit + is_normal

    taux_effectif = (montant_is / benefice * 100) if benefice > 0 else 0

    return {
        "montant_is": round(montant_is, 2),
        "taux_effectif": round(taux_effectif, 2),
        "detail": {
            "part_taux_reduit": round(part_taux_reduit, 2),
            "is_sur_part_reduite": round(is_reduit, 2),
            "part_taux_normal": round(part_taux_normal, 2),
            "is_sur_part_normale": round(is_normal, 2),
        }
    }


def calculer_flat_tax(dividendes_bruts: float) -> dict:
    """
    Calcule la flat tax (PFU) sur les dividendes - taux 2026 : 30% (31.4% avec PS).

    Args:
        dividendes_bruts: montant brut des dividendes distribués

    Returns:
        dict avec montant_flat_tax, dividendes_nets
    """
    taux = CONFIG["flat_tax"]["taux_global"]
    montant = dividendes_bruts * taux
    net = dividendes_bruts - montant

    return {
        "dividendes_bruts": round(dividendes_bruts, 2),
        "montant_flat_tax": round(montant, 2),
        "dividendes_nets": round(net, 2),
        "taux_applique": taux,
    }