"""
income.py — Calcul du revenu net disponible pour chaque statut juridique
Barèmes 2026 — avec détail mensuel salaire/dividendes et option IR/IS
"""

import json
from pathlib import Path
from core.tax import calculer_ir, calculer_is, calculer_flat_tax


def _charger_config() -> dict:
    chemin = Path(__file__).parent.parent / "data" / "config.json"
    with open(chemin, "r", encoding="utf-8") as f:
        return json.load(f)


CONFIG = _charger_config()


def _detail_mensuel(salaire_brut_annuel: float, salaire_net_annuel: float,
                    cotisations_annuelles: float, impot_revenu_annuel: float,
                    dividendes_bruts_annuels: float, flat_tax_annuelle: float,
                    dividendes_nets_annuels: float) -> dict:
    """Génère le détail mensuel pour l'affichage."""
    return {
        "salaire_brut_mensuel":      round(salaire_brut_annuel / 12, 2),
        "cotisations_mensuelles":    round(cotisations_annuelles / 12, 2),
        "salaire_net_mensuel":       round(salaire_net_annuel / 12, 2),
        "impot_revenu_mensuel":      round(impot_revenu_annuel / 12, 2),
        "salaire_net_apres_ir":      round((salaire_net_annuel - impot_revenu_annuel) / 12, 2),
        "dividendes_bruts_mensuel":  round(dividendes_bruts_annuels / 12, 2),
        "flat_tax_mensuelle":        round(flat_tax_annuelle / 12, 2),
        "dividendes_nets_mensuel":   round(dividendes_nets_annuels / 12, 2),
        "revenu_total_mensuel":      round((salaire_net_annuel - impot_revenu_annuel + dividendes_nets_annuels) / 12, 2),
    }


def simuler_micro(ca: float, type_activite: str, nb_parts: float = 1.0) -> dict:
    """Micro-entreprise — IR uniquement, pas d'IS possible."""
    cfg_micro = CONFIG["micro_entreprise"]
    plafond = cfg_micro[f"plafond_ca_{type_activite}"]
    eligible = ca <= plafond

    taux_abattement = cfg_micro["abattements"][type_activite]
    revenu_imposable = ca * (1 - taux_abattement)

    taux_coti = cfg_micro["taux_cotisations_sur_ca"][type_activite]
    cotisations = ca * taux_coti

    ir_result = calculer_ir(revenu_imposable, nb_parts)
    montant_ir = ir_result["montant_ir"]

    revenu_net = ca - cotisations - montant_ir

    # En micro, le "salaire" = CA - cotisations (revenu avant IR)
    revenu_avant_ir = ca - cotisations
    detail = _detail_mensuel(
        salaire_brut_annuel=ca,
        salaire_net_annuel=revenu_avant_ir,
        cotisations_annuelles=cotisations,
        impot_revenu_annuel=montant_ir,
        dividendes_bruts_annuels=0,
        flat_tax_annuelle=0,
        dividendes_nets_annuels=0,
    )

    return {
        "statut": "Micro-entreprise",
        "regime_fiscal": "IR",
        "eligible": eligible,
        "plafond_ca": plafond,
        "ca": round(ca, 2),
        "abattement_forfaitaire": round(ca * taux_abattement, 2),
        "revenu_imposable": round(revenu_imposable, 2),
        "cotisations_sociales": round(cotisations, 2),
        "impot_revenu": round(montant_ir, 2),
        "impot_societes": 0,
        "flat_tax_dividendes": 0,
        "dividendes_bruts": 0,
        "dividendes_nets": 0,
        "revenu_net_disponible": round(revenu_net, 2),
        "tmi": ir_result["tmi"],
        "taux_moyen_ir": ir_result["taux_moyen"],
        "regime_social": "TNS (SSI)",
        "mensuel": detail,
    }


def simuler_eurl(
    ca: float,
    charges_deductibles: float,
    remuneration_dirigeant: float,
    dividendes: float,
    nb_parts: float = 1.0,
    capital_social: float = 1000,
    regime_fiscal: str = "IS",   # "IS" ou "IR"
) -> dict:
    """
    EURL — IS ou IR au choix.

    En IR : le bénéfice est imposé directement au barème progressif (comme une EI).
    En IS : taux 15%/25%, puis flat tax sur dividendes.
    """
    cfg_tns = CONFIG["cotisations_tns"]

    # ── Cotisations TNS sur rémunération ──
    cotisations_remuneration = remuneration_dirigeant * (cfg_tns["cout_total_pour_1000_net"] / 1000 - 1)
    salaire_brut = remuneration_dirigeant + cotisations_remuneration  # coût total pour la société

    if regime_fiscal == "IS":
        # Seuil dividendes soumis à cotisations TNS (10% du capital social)
        seuil_div_tns = capital_social * cfg_tns["seuil_dividendes_soumis_cotisations_pct"]
        dividendes_soumis_tns = max(0, dividendes - seuil_div_tns)
        cotisations_tns_div = dividendes_soumis_tns * (cfg_tns["cout_total_pour_1000_net"] / 1000 - 1)
        total_cotisations = cotisations_remuneration + cotisations_tns_div

        benefice_imposable = ca - charges_deductibles - salaire_brut - cotisations_tns_div
        benefice_apres_dividendes = max(0, benefice_imposable - dividendes)

        is_result = calculer_is(benefice_apres_dividendes)
        montant_is = is_result["montant_is"]

        flat_tax_result = calculer_flat_tax(dividendes)
        montant_flat_tax = flat_tax_result["montant_flat_tax"]
        dividendes_nets = flat_tax_result["dividendes_nets"]

        ir_result = calculer_ir(remuneration_dirigeant, nb_parts)
        montant_ir = ir_result["montant_ir"]

        revenu_net = remuneration_dirigeant - montant_ir + dividendes_nets

        detail = _detail_mensuel(
            salaire_brut_annuel=salaire_brut,
            salaire_net_annuel=remuneration_dirigeant,
            cotisations_annuelles=cotisations_remuneration,
            impot_revenu_annuel=montant_ir,
            dividendes_bruts_annuels=dividendes,
            flat_tax_annuelle=montant_flat_tax,
            dividendes_nets_annuels=dividendes_nets,
        )

        return {
            "statut": "EURL (IS)",
            "regime_fiscal": "IS",
            "eligible": True,
            "ca": round(ca, 2),
            "charges_deductibles": round(charges_deductibles, 2),
            "salaire_brut_annuel": round(salaire_brut, 2),
            "remuneration_nette_dirigeant": round(remuneration_dirigeant, 2),
            "cotisations_tns_remuneration": round(cotisations_remuneration, 2),
            "cotisations_tns_dividendes": round(cotisations_tns_div, 2),
            "cotisations_sociales": round(total_cotisations, 2),
            "benefice_imposable": round(max(0, benefice_imposable), 2),
            "impot_societes": round(montant_is, 2),
            "dividendes_bruts": round(dividendes, 2),
            "flat_tax_dividendes": round(montant_flat_tax, 2),
            "dividendes_nets": round(dividendes_nets, 2),
            "impot_revenu": round(montant_ir, 2),
            "revenu_net_disponible": round(revenu_net, 2),
            "tmi": ir_result["tmi"],
            "taux_moyen_ir": ir_result["taux_moyen"],
            "regime_social": "TNS (SSI)",
            "seuil_dividendes_tns": round(seuil_div_tns, 2),
            "mensuel": detail,
        }

    else:  # IR
        # En EURL à l'IR, pas d'IS : le bénéfice entier est imposé au barème progressif
        # Les dividendes ne sont pas possibles en IR (tout est bénéfice imposé à l'IR)
        benefice = max(0, ca - charges_deductibles - salaire_brut)
        # En IR, la rémunération = bénéfice (pas de séparation société/dirigeant)
        revenu_imposable = benefice  # le gérant est imposé sur le bénéfice total
        ir_result = calculer_ir(revenu_imposable, nb_parts)
        montant_ir = ir_result["montant_ir"]

        revenu_net = benefice - cotisations_remuneration - montant_ir

        detail = _detail_mensuel(
            salaire_brut_annuel=salaire_brut,
            salaire_net_annuel=benefice,
            cotisations_annuelles=cotisations_remuneration,
            impot_revenu_annuel=montant_ir,
            dividendes_bruts_annuels=0,
            flat_tax_annuelle=0,
            dividendes_nets_annuels=0,
        )

        return {
            "statut": "EURL (IR)",
            "regime_fiscal": "IR",
            "eligible": True,
            "ca": round(ca, 2),
            "charges_deductibles": round(charges_deductibles, 2),
            "salaire_brut_annuel": round(salaire_brut, 2),
            "remuneration_nette_dirigeant": round(remuneration_dirigeant, 2),
            "cotisations_tns_remuneration": round(cotisations_remuneration, 2),
            "cotisations_tns_dividendes": 0,
            "cotisations_sociales": round(cotisations_remuneration, 2),
            "benefice_imposable": round(benefice, 2),
            "impot_societes": 0,
            "dividendes_bruts": 0,
            "flat_tax_dividendes": 0,
            "dividendes_nets": 0,
            "impot_revenu": round(montant_ir, 2),
            "revenu_net_disponible": round(revenu_net, 2),
            "tmi": ir_result["tmi"],
            "taux_moyen_ir": ir_result["taux_moyen"],
            "regime_social": "TNS (SSI)",
            "mensuel": detail,
        }


def simuler_sasu(
    ca: float,
    charges_deductibles: float,
    salaire_net: float,
    dividendes: float,
    nb_parts: float = 1.0,
    regime_fiscal: str = "IS",   # "IS" ou "IR"
) -> dict:
    """
    SASU — IS par défaut, IR sur option (5 premiers exercices).

    En IR : le bénéfice imposé directement au barème (rare mais possible).
    En IS : taux 15%/25%, flat tax sur dividendes, pas de cotisations sur dividendes.
    """
    cfg_salarie = CONFIG["cotisations_assimile_salarie"]

    cotisations_salaire = salaire_net * (cfg_salarie["cout_total_pour_1000_net"] / 1000 - 1)
    salaire_brut = salaire_net + cotisations_salaire

    # Trimestres retraite validés
    pass_trimestre = CONFIG["retraite"]["salaire_brut_min_1_trimestre"]
    trimestres_valides = min(4, int(salaire_brut / pass_trimestre))

    if regime_fiscal == "IS":
        benefice_imposable = ca - charges_deductibles - salaire_brut
        benefice_apres_dividendes = max(0, benefice_imposable - dividendes)

        is_result = calculer_is(benefice_apres_dividendes)
        montant_is = is_result["montant_is"]

        flat_tax_result = calculer_flat_tax(dividendes)
        montant_flat_tax = flat_tax_result["montant_flat_tax"]
        dividendes_nets = flat_tax_result["dividendes_nets"]

        ir_result = calculer_ir(salaire_net, nb_parts)
        montant_ir = ir_result["montant_ir"]

        revenu_net = salaire_net - montant_ir + dividendes_nets

        detail = _detail_mensuel(
            salaire_brut_annuel=salaire_brut,
            salaire_net_annuel=salaire_net,
            cotisations_annuelles=cotisations_salaire,
            impot_revenu_annuel=montant_ir,
            dividendes_bruts_annuels=dividendes,
            flat_tax_annuelle=montant_flat_tax,
            dividendes_nets_annuels=dividendes_nets,
        )

        return {
            "statut": "SASU (IS)",
            "regime_fiscal": "IS",
            "eligible": True,
            "ca": round(ca, 2),
            "charges_deductibles": round(charges_deductibles, 2),
            "salaire_brut_annuel": round(salaire_brut, 2),
            "salaire_net_president": round(salaire_net, 2),
            "cotisations_assimile_salarie": round(cotisations_salaire, 2),
            "cotisations_sociales": round(cotisations_salaire, 2),
            "benefice_imposable": round(max(0, benefice_imposable), 2),
            "impot_societes": round(montant_is, 2),
            "dividendes_bruts": round(dividendes, 2),
            "flat_tax_dividendes": round(montant_flat_tax, 2),
            "dividendes_nets": round(dividendes_nets, 2),
            "impot_revenu": round(montant_ir, 2),
            "revenu_net_disponible": round(revenu_net, 2),
            "tmi": ir_result["tmi"],
            "taux_moyen_ir": ir_result["taux_moyen"],
            "regime_social": "Assimilé salarié (Régime général)",
            "trimestres_retraite_valides": trimestres_valides,
            "mensuel": detail,
        }

    else:  # IR (option rare, 5 premiers exercices)
        benefice = max(0, ca - charges_deductibles - salaire_brut)
        ir_result = calculer_ir(benefice, nb_parts)
        montant_ir = ir_result["montant_ir"]
        revenu_net = benefice - cotisations_salaire - montant_ir

        detail = _detail_mensuel(
            salaire_brut_annuel=salaire_brut,
            salaire_net_annuel=benefice,
            cotisations_annuelles=cotisations_salaire,
            impot_revenu_annuel=montant_ir,
            dividendes_bruts_annuels=0,
            flat_tax_annuelle=0,
            dividendes_nets_annuels=0,
        )

        return {
            "statut": "SASU (IR)",
            "regime_fiscal": "IR",
            "eligible": True,
            "ca": round(ca, 2),
            "charges_deductibles": round(charges_deductibles, 2),
            "salaire_brut_annuel": round(salaire_brut, 2),
            "salaire_net_president": round(salaire_net, 2),
            "cotisations_assimile_salarie": round(cotisations_salaire, 2),
            "cotisations_sociales": round(cotisations_salaire, 2),
            "benefice_imposable": round(benefice, 2),
            "impot_societes": 0,
            "dividendes_bruts": 0,
            "flat_tax_dividendes": 0,
            "dividendes_nets": 0,
            "impot_revenu": round(montant_ir, 2),
            "revenu_net_disponible": round(revenu_net, 2),
            "tmi": ir_result["tmi"],
            "taux_moyen_ir": ir_result["taux_moyen"],
            "regime_social": "Assimilé salarié (Régime général)",
            "trimestres_retraite_valides": trimestres_valides,
            "mensuel": detail,
        }