"""
income.py — Calcul du revenu net disponible pour chaque statut juridique
Barèmes 2026
"""

import json
from pathlib import Path
from core.tax import calculer_ir, calculer_is, calculer_flat_tax


def _charger_config() -> dict:
    chemin = Path(__file__).parent.parent / "data" / "config.json"
    with open(chemin, "r", encoding="utf-8") as f:
        return json.load(f)


CONFIG = _charger_config()


def simuler_micro(ca: float, type_activite: str, nb_parts: float = 1.0) -> dict:
    """
    Simule le revenu net en micro-entreprise.

    Args:
        ca: chiffre d'affaires annuel HT (€)
        type_activite: 'commerce', 'services_bic' ou 'services_bnc'
        nb_parts: quotient familial du foyer

    Returns:
        dict complet avec tous les détails de calcul
    """
    cfg_micro = CONFIG["micro_entreprise"]

    # Vérification plafonds
    plafond = cfg_micro[f"plafond_ca_{type_activite}"]
    eligible = ca <= plafond

    # Abattement forfaitaire
    taux_abattement = cfg_micro["abattements"][type_activite]
    revenu_imposable = ca * (1 - taux_abattement)

    # Cotisations sociales sur CA
    taux_coti = cfg_micro["taux_cotisations_sur_ca"][type_activite]
    cotisations = ca * taux_coti

    # Impôt sur le revenu
    ir_result = calculer_ir(revenu_imposable, nb_parts)
    montant_ir = ir_result["montant_ir"]

    # Revenu net disponible
    revenu_net = ca - cotisations - montant_ir

    return {
        "statut": "Micro-entreprise",
        "eligible": eligible,
        "plafond_ca": plafond,
        "ca": round(ca, 2),
        "abattement_forfaitaire": round(ca * taux_abattement, 2),
        "revenu_imposable": round(revenu_imposable, 2),
        "cotisations_sociales": round(cotisations, 2),
        "impot_revenu": round(montant_ir, 2),
        "impot_societes": 0,
        "flat_tax_dividendes": 0,
        "dividendes_nets": 0,
        "revenu_net_disponible": round(revenu_net, 2),
        "tmi": ir_result["tmi"],
        "taux_moyen_ir": ir_result["taux_moyen"],
        "charges_deductibles": False,
        "regime_social": "TNS (SSI)",
        "regime_fiscal": "IR",
    }


def simuler_eurl_is(
    ca: float,
    charges_deductibles: float,
    remuneration_dirigeant: float,
    dividendes: float,
    nb_parts: float = 1.0,
    capital_social: float = 1000,
) -> dict:
    """
    Simule le revenu net en EURL soumise à l'IS.

    Args:
        ca: chiffre d'affaires annuel HT (€)
        charges_deductibles: charges pro déductibles hors rémunération (€)
        remuneration_dirigeant: rémunération nette souhaitée du dirigeant (€)
        dividendes: montant brut de dividendes à distribuer (€)
        nb_parts: quotient familial du foyer
        capital_social: capital social de l'EURL (€) — sert au calcul du seuil dividendes soumis à cotisations TNS

    Returns:
        dict complet avec tous les détails de calcul
    """
    cfg_tns = CONFIG["cotisations_tns"]

    # Cotisations TNS sur rémunération nette
    cotisations_remuneration = remuneration_dirigeant * (cfg_tns["cout_total_pour_1000_net"] / 1000 - 1)
    cout_total_remuneration = remuneration_dirigeant + cotisations_remuneration

    # Seuil dividendes soumis à cotisations TNS : 10% du capital social
    seuil_dividendes_tns = capital_social * cfg_tns["seuil_dividendes_soumis_cotisations_pct"]
    dividendes_soumis_tns = max(0, dividendes - seuil_dividendes_tns)
    dividendes_hors_tns = min(dividendes, seuil_dividendes_tns)
    cotisations_tns_dividendes = dividendes_soumis_tns * (cfg_tns["cout_total_pour_1000_net"] / 1000 - 1)

    total_cotisations = cotisations_remuneration + cotisations_tns_dividendes

    # Bénéfice imposable société
    benefice_imposable = ca - charges_deductibles - cout_total_remuneration - cotisations_tns_dividendes

    # IS
    is_result = calculer_is(max(0, benefice_imposable - dividendes))
    montant_is = is_result["montant_is"]

    # Flat tax sur dividendes
    flat_tax_result = calculer_flat_tax(dividendes)
    montant_flat_tax = flat_tax_result["montant_flat_tax"]
    dividendes_nets = flat_tax_result["dividendes_nets"]

    # IR sur rémunération
    ir_result = calculer_ir(remuneration_dirigeant, nb_parts)
    montant_ir = ir_result["montant_ir"]

    revenu_net_disponible = remuneration_dirigeant - montant_ir + dividendes_nets

    return {
        "statut": "EURL (IS)",
        "eligible": True,
        "ca": round(ca, 2),
        "charges_deductibles": round(charges_deductibles, 2),
        "remuneration_nette_dirigeant": round(remuneration_dirigeant, 2),
        "cotisations_tns_remuneration": round(cotisations_remuneration, 2),
        "cotisations_tns_dividendes": round(cotisations_tns_dividendes, 2),
        "cotisations_sociales": round(total_cotisations, 2),
        "benefice_imposable": round(max(0, benefice_imposable), 2),
        "impot_societes": round(montant_is, 2),
        "dividendes_bruts": round(dividendes, 2),
        "flat_tax_dividendes": round(montant_flat_tax, 2),
        "dividendes_nets": round(dividendes_nets, 2),
        "impot_revenu": round(montant_ir, 2),
        "revenu_net_disponible": round(revenu_net_disponible, 2),
        "tmi": ir_result["tmi"],
        "taux_moyen_ir": ir_result["taux_moyen"],
        "regime_social": "TNS (SSI)",
        "regime_fiscal": "IS",
        "seuil_dividendes_tns": round(seuil_dividendes_tns, 2),
    }


def simuler_sasu_is(
    ca: float,
    charges_deductibles: float,
    salaire_net: float,
    dividendes: float,
    nb_parts: float = 1.0,
) -> dict:
    """
    Simule le revenu net en SASU soumise à l'IS.

    Args:
        ca: chiffre d'affaires annuel HT (€)
        charges_deductibles: charges pro déductibles hors rémunération (€)
        salaire_net: salaire net souhaité du président (€)
        dividendes: montant brut de dividendes à distribuer (€)
        nb_parts: quotient familial du foyer

    Returns:
        dict complet avec tous les détails de calcul
    """
    cfg_salarie = CONFIG["cotisations_assimile_salarie"]

    # Cotisations assimilé salarié
    cotisations_salaire = salaire_net * (cfg_salarie["cout_total_pour_1000_net"] / 1000 - 1)
    cout_total_salaire = salaire_net + cotisations_salaire

    # Bénéfice imposable société
    benefice_imposable = ca - charges_deductibles - cout_total_salaire

    # IS
    is_result = calculer_is(max(0, benefice_imposable - dividendes))
    montant_is = is_result["montant_is"]

    # Flat tax dividendes (pas de cotisations sociales sur dividendes en SASU)
    flat_tax_result = calculer_flat_tax(dividendes)
    montant_flat_tax = flat_tax_result["montant_flat_tax"]
    dividendes_nets = flat_tax_result["dividendes_nets"]

    # IR sur salaire net
    ir_result = calculer_ir(salaire_net, nb_parts)
    montant_ir = ir_result["montant_ir"]

    revenu_net_disponible = salaire_net - montant_ir + dividendes_nets

    # Trimestres retraite validés
    salaire_brut_annuel = salaire_net * 1.82  # approximation
    pass_2026 = CONFIG["retraite"]["salaire_brut_min_4_trimestres"]
    trimestres_valides = min(4, int(salaire_brut_annuel / (pass_2026 / 4)))

    return {
        "statut": "SASU (IS)",
        "eligible": True,
        "ca": round(ca, 2),
        "charges_deductibles": round(charges_deductibles, 2),
        "salaire_net_president": round(salaire_net, 2),
        "cotisations_assimile_salarie": round(cotisations_salaire, 2),
        "cotisations_sociales": round(cotisations_salaire, 2),
        "benefice_imposable": round(max(0, benefice_imposable), 2),
        "impot_societes": round(montant_is, 2),
        "dividendes_bruts": round(dividendes, 2),
        "flat_tax_dividendes": round(montant_flat_tax, 2),
        "dividendes_nets": round(dividendes_nets, 2),
        "impot_revenu": round(montant_ir, 2),
        "revenu_net_disponible": round(revenu_net_disponible, 2),
        "tmi": ir_result["tmi"],
        "taux_moyen_ir": ir_result["taux_moyen"],
        "regime_social": "Assimilé salarié (Régime général)",
        "regime_fiscal": "IS",
        "trimestres_retraite_valides": trimestres_valides,
    }