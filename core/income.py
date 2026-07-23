"""
income.py — Calcul détaillé par statut juridique — Barèmes 2026

Corrections v3 :
- SASU : TNS supprimé — le président de SASU est TOUJOURS assimilé salarié
- EURL IS dividendes : calcul correct de la flat tax selon la part soumise ou non aux cotisations SSI
  - Part ≤ seuil (10% capital) : IR 12,8% + prélèvements sociaux 17,2% + PS 1,4%
  - Part > seuil              : cotisations SSI 45% + IR 12,8% seulement (les PS 17,2% sont remplacés)
- IS calculé sur bénéfice AVANT distribution de dividendes
"""

import json
from pathlib import Path
from core.tax import calculer_ir, calculer_is

def _charger_config() -> dict:
    chemin = Path(__file__).parent.parent / "data" / "config.json"
    with open(chemin, "r", encoding="utf-8") as f:
        return json.load(f)

CONFIG = _charger_config()


def _flat_tax_partielle(montant: float) -> dict:
    """Flat tax complète (PFU 12,8% + PS 17,2% + prél. 1,4% = 31,4%)."""
    cfg = CONFIG["flat_tax"]["detail"]
    ir_pfu  = round(montant * cfg["pfu_ir"], 2)
    ps      = round(montant * (cfg["csg_crds"] + cfg["prelevement_social"]), 2)
    total   = round(ir_pfu + ps, 2)
    return {"ir_pfu": ir_pfu, "ps": ps, "total": total, "net": round(montant - total, 2)}


def _flat_tax_sans_ps(montant: float) -> dict:
    """Flat tax sans prélèvements sociaux (car remplacés par cotisations SSI)."""
    cfg = CONFIG["flat_tax"]["detail"]
    ir_pfu = round(montant * cfg["pfu_ir"], 2)
    return {"ir_pfu": ir_pfu, "ps": 0, "total": ir_pfu, "net": round(montant - ir_pfu, 2)}


# ─────────────────────────────────────────────────────────────────────────────
# MICRO-ENTREPRISE
# ─────────────────────────────────────────────────────────────────────────────
def simuler_micro(ca: float, type_activite: str, nb_parts: float = 1.0) -> dict:
    cfg          = CONFIG["micro_entreprise"]
    plafond      = cfg[f"plafond_ca_{type_activite}"]
    taux_abt     = cfg["abattements"][type_activite]
    taux_coti    = cfg["taux_cotisations_sur_ca"][type_activite]

    abattement       = round(ca * taux_abt, 2)
    cotisations      = round(ca * taux_coti, 2)
    revenu_imposable = round(ca * (1 - taux_abt), 2)

    ir         = calculer_ir(revenu_imposable, nb_parts)
    montant_ir = ir["montant_ir"]
    revenu_net = round(max(0, ca - cotisations - montant_ir), 2)

    return {
        "statut"        : "Micro-entreprise",
        "regime_fiscal" : "IR",
        "regime_social" : "TNS (SSI)",
        "eligible"      : ca <= plafond,
        "plafond_ca"    : plafond,

        "entreprise": {
            "ca"                    : round(ca, 2),
            "abattement_forfaitaire": abattement,
            "taux_abattement"       : taux_abt,
            "charges_deductibles"   : 0,
            "regime_fiscal"         : "IR (barème progressif)",
            "base_imposable_ir"     : revenu_imposable,
            "impot_societes"        : 0,
            "taux_is_effectif"      : 0,
            "reste_apres_impots"    : revenu_imposable,
        },

        "salaire": {
            "applicable"                 : True,
            "mode_ir"                    : True,
            "remuneration_brute"         : round(ca - cotisations, 2),
            "taux_cotisations"           : taux_coti,
            "cotisations"                : cotisations,
            "detail_cotisations"         : f"Cotisations TNS sur CA ({taux_coti*100:.1f}% × CA)",
            "remuneration_nette"         : round(ca - cotisations, 2),
            "ir_personnel"               : montant_ir,
            "tmi"                        : ir["tmi"],
            "taux_moyen_ir"              : ir["taux_moyen"],
            "remuneration_nette_apres_ir": revenu_net,
            "total_impots_boite_salaire" : 0,
        },

        "dividendes": {
            "applicable": False,
            "raison"    : "Dividendes impossibles en micro-entreprise",
        },

        "tresorerie": {
            "applicable"  : False,
            "raison"      : "Pas de société distincte en micro-entreprise",
            "compte_boite": 0,
        },

        "synthese": {
            "revenu_net_disponible"   : revenu_net,
            "total_impots_et_charges" : round(cotisations + montant_ir, 2),
            "tmi"                     : ir["tmi"],
            "taux_moyen_ir"           : ir["taux_moyen"],
            "trimestres_retraite"     : None,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# EURL
# ─────────────────────────────────────────────────────────────────────────────
def simuler_eurl(
    ca: float,
    charges_deductibles: float,
    remuneration_net: float,
    dividendes_bruts: float,
    nb_parts: float       = 1.0,
    capital_social: float = 1000,
    regime_fiscal: str    = "IS",
) -> dict:
    cfg_tns   = CONFIG["cotisations_tns"]
    taux_cout = cfg_tns["cout_total_pour_1000_net"] / 1000   # 1.45
    taux_coti = cfg_tns["taux_global_sur_net"]               # 0.45
    taux_ssi  = taux_coti                                    # taux SSI appliqué aux dividendes

    if regime_fiscal == "IS":
        # ── Cotisations TNS sur salaire ──────────────────────────────────
        cotisations_sal = round(remuneration_net * (taux_cout - 1), 2)
        salaire_brut    = round(remuneration_net + cotisations_sal, 2)

        # ── IS : sur bénéfice AVANT dividendes ───────────────────────────
        benef_imposable_is = round(max(0, ca - charges_deductibles - salaire_brut), 2)
        is_res             = calculer_is(benef_imposable_is)
        montant_is         = is_res["montant_is"]

        # ── Bénéfice après IS = montant distribuable ─────────────────────
        benef_apres_is = round(max(0, benef_imposable_is - montant_is), 2)
        dividendes_bruts = round(min(dividendes_bruts, benef_apres_is), 2)

        # ── Seuil TNS : 10% du capital social ────────────────────────────
        seuil_tns    = round(capital_social * cfg_tns["seuil_dividendes_soumis_cotisations_pct"], 2)
        div_sous_seuil  = round(min(dividendes_bruts, seuil_tns), 2)   # part classique
        div_hors_seuil  = round(max(0, dividendes_bruts - seuil_tns), 2)  # part soumise SSI

        # ── Cotisations SSI sur dividendes (part > seuil) ────────────────
        # Les cotisations SSI sont calculées sur le montant brut de dividendes excédant le seuil
        cotisations_div = round(div_hors_seuil * taux_ssi, 2)

        # ── Flat tax sur part ≤ seuil (IR 12,8% + PS 17,2% + prél. 1,4%)
        ft_sous_seuil   = _flat_tax_partielle(div_sous_seuil)

        # ── Flat tax sur part > seuil : IR 12,8% seulement (PS remplacés par SSI)
        ft_hors_seuil   = _flat_tax_sans_ps(div_hors_seuil)

        montant_ft_total  = round(ft_sous_seuil["total"] + ft_hors_seuil["total"], 2)
        ir_pfu_total      = round(ft_sous_seuil["ir_pfu"] + ft_hors_seuil["ir_pfu"], 2)
        ps_total          = ft_sous_seuil["ps"]   # PS uniquement sur part ≤ seuil

        dividendes_nets   = round(
            dividendes_bruts - cotisations_div - montant_ft_total, 2
        )
        dividendes_nets   = max(0, dividendes_nets)

        # ── IR personnel sur salaire seul ─────────────────────────────────
        ir         = calculer_ir(remuneration_net, nb_parts)
        montant_ir = ir["montant_ir"]

        # ── Trésorerie ────────────────────────────────────────────────────
        tresorerie = round(max(0, benef_apres_is - dividendes_bruts), 2)

        # ── Revenu net perso ──────────────────────────────────────────────
        revenu_net = round(max(0, remuneration_net - montant_ir + dividendes_nets), 2)

        total_cotisations = round(cotisations_sal + cotisations_div, 2)

        return {
            "statut"        : "EURL (IS)",
            "regime_fiscal" : "IS",
            "regime_social" : "TNS (SSI)",
            "eligible"      : True,

            "entreprise": {
                "ca"                    : round(ca, 2),
                "charges_deductibles"   : round(charges_deductibles, 2),
                "abattement_forfaitaire": 0,
                "taux_abattement"       : 0,
                "regime_fiscal"         : "IS (15% ≤ 42 500€ · 25% au-delà)",
                "base_imposable_is"     : benef_imposable_is,
                "impot_societes"        : montant_is,
                "taux_is_effectif"      : is_res["taux_effectif"],
                "reste_apres_impots"    : benef_apres_is,
            },

            "salaire": {
                "applicable"                 : True,
                "mode_ir"                    : False,
                "salaire_net_saisi"          : round(remuneration_net, 2),
                "taux_cotisations"           : taux_coti,
                "cotisations"                : cotisations_sal,
                "detail_cotisations"         : f"Cotisations TNS ({taux_coti*100:.0f}% du net)",
                "salaire_brut"               : salaire_brut,
                "ir_personnel"               : montant_ir,
                "tmi"                        : ir["tmi"],
                "taux_moyen_ir"              : ir["taux_moyen"],
                "salaire_net_apres_ir"       : round(max(0, remuneration_net - montant_ir), 2),
                "total_impots_boite_salaire" : cotisations_sal,
            },

            "dividendes": {
                "applicable"            : True,
                "dividendes_bruts"      : round(dividendes_bruts, 2),
                "seuil_tns"             : seuil_tns,
                "div_sous_seuil"        : div_sous_seuil,
                "div_hors_seuil"        : div_hors_seuil,
                # Part ≤ seuil : flat tax complète
                "ft_sous_seuil_ir"      : ft_sous_seuil["ir_pfu"],
                "ft_sous_seuil_ps"      : ft_sous_seuil["ps"],
                "ft_sous_seuil_total"   : ft_sous_seuil["total"],
                # Part > seuil : cotisations SSI + IR PFU seulement
                "cotisations_ssi_div"   : cotisations_div,
                "ft_hors_seuil_ir"      : ft_hors_seuil["ir_pfu"],
                "ft_hors_seuil_ps"      : 0,
                "ft_hors_seuil_total"   : ft_hors_seuil["total"],
                # Totaux
                "montant_flat_tax"      : montant_ft_total,
                "ir_pfu_total"          : ir_pfu_total,
                "ps_total"              : ps_total,
                "cotisations_tns_div"   : cotisations_div,
                "dividendes_nets"       : dividendes_nets,
                "total_impots_dividendes": round(cotisations_div + montant_ft_total, 2),
                "detail_flat_tax"       : (
                    f"Part ≤ {seuil_tns:,.0f}€ : flat tax complète 31,4%  |  "
                    f"Part > {seuil_tns:,.0f}€ : SSI {taux_ssi*100:.0f}% + IR PFU 12,8% (sans PS)"
                ),
            },

            "tresorerie": {
                "applicable"  : True,
                "compte_boite": tresorerie,
                "detail"      : f"Bénéf. IS {benef_imposable_is:,.0f}€ − IS {montant_is:,.0f}€ = {benef_apres_is:,.0f}€ − dividendes {dividendes_bruts:,.0f}€",
            },

            "synthese": {
                "revenu_net_disponible"  : revenu_net,
                "total_impots_et_charges": round(total_cotisations + montant_is + montant_ft_total + montant_ir, 2),
                "tmi"                    : ir["tmi"],
                "taux_moyen_ir"          : ir["taux_moyen"],
                "trimestres_retraite"    : None,
            },
        }

    else:  # IR
        benef_avant_coti = round(max(0, ca - charges_deductibles), 2)
        cotisations_sal  = round(benef_avant_coti * taux_coti / (1 + taux_coti), 2)
        benef_imposable  = round(max(0, benef_avant_coti - cotisations_sal), 2)

        ir         = calculer_ir(benef_imposable, nb_parts)
        montant_ir = ir["montant_ir"]
        revenu_net = round(max(0, benef_imposable - montant_ir), 2)

        return {
            "statut"        : "EURL (IR)",
            "regime_fiscal" : "IR",
            "regime_social" : "TNS (SSI)",
            "eligible"      : True,

            "entreprise": {
                "ca"                    : round(ca, 2),
                "charges_deductibles"   : round(charges_deductibles, 2),
                "abattement_forfaitaire": 0,
                "taux_abattement"       : 0,
                "regime_fiscal"         : "IR (barème progressif — tout le bénéfice imposé au dirigeant)",
                "base_imposable_ir"     : benef_imposable,
                "impot_societes"        : 0,
                "taux_is_effectif"      : 0,
                "reste_apres_impots"    : benef_imposable,
            },

            "salaire": {
                "applicable"                 : True,
                "mode_ir"                    : True,
                "remuneration_brute"         : benef_avant_coti,
                "taux_cotisations"           : taux_coti,
                "cotisations"                : cotisations_sal,
                "detail_cotisations"         : f"Cotisations TNS (~{taux_coti*100:.0f}% du bénéfice)",
                "remuneration_nette"         : benef_imposable,
                "ir_personnel"               : montant_ir,
                "tmi"                        : ir["tmi"],
                "taux_moyen_ir"              : ir["taux_moyen"],
                "remuneration_nette_apres_ir": revenu_net,
                "total_impots_boite_salaire" : cotisations_sal,
            },

            "dividendes": {
                "applicable": False,
                "raison"    : "Dividendes non disponibles à l'IR",
            },

            "tresorerie": {
                "applicable"  : False,
                "raison"      : "En IR, tout le bénéfice est imposé au dirigeant — pas de trésorerie séparée",
                "compte_boite": 0,
            },

            "synthese": {
                "revenu_net_disponible"  : revenu_net,
                "total_impots_et_charges": round(cotisations_sal + montant_ir, 2),
                "tmi"                    : ir["tmi"],
                "taux_moyen_ir"          : ir["taux_moyen"],
                "trimestres_retraite"    : None,
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# SASU — assimilé salarié uniquement (président SASU = toujours régime général)
# ─────────────────────────────────────────────────────────────────────────────
def simuler_sasu(
    ca: float,
    charges_deductibles: float,
    salaire_net: float,
    dividendes_bruts: float,
    nb_parts: float    = 1.0,
    regime_fiscal: str = "IS",
) -> dict:
    """
    SASU : le président est TOUJOURS assimilé salarié (régime général).
    Pas de TNS possible en SASU unipersonnelle.
    Dividendes non soumis aux cotisations sociales (flat tax 31,4% uniquement).
    """
    cfg_rs    = CONFIG["cotisations_assimile_salarie"]
    label_rs  = "Assimilé salarié (Régime général)"
    detail_rs = f"Charges sociales assimilé salarié ({cfg_rs['taux_global_sur_net']*100:.0f}% du net)"
    taux_cout = cfg_rs["cout_total_pour_1000_net"] / 1000
    taux_coti = cfg_rs["taux_global_sur_net"]

    if regime_fiscal == "IS":
        cotisations  = round(salaire_net * (taux_cout - 1), 2)
        salaire_brut = round(salaire_net + cotisations, 2)

        pass_trim  = CONFIG["retraite"]["salaire_brut_min_1_trimestre"]
        trimestres = min(4, int(salaire_brut / pass_trim)) if salaire_brut > 0 else 0

        # IS sur bénéfice AVANT dividendes
        benef_imposable_is = round(max(0, ca - charges_deductibles - salaire_brut), 2)
        is_res             = calculer_is(benef_imposable_is)
        montant_is         = is_res["montant_is"]

        benef_apres_is   = round(max(0, benef_imposable_is - montant_is), 2)
        dividendes_bruts = round(min(dividendes_bruts, benef_apres_is), 2)

        # Flat tax complète sur dividendes (pas de cotisations sociales en SASU)
        ft           = _flat_tax_partielle(dividendes_bruts)
        montant_ft   = ft["total"]
        dividendes_nets = ft["net"]

        ir         = calculer_ir(salaire_net, nb_parts)
        montant_ir = ir["montant_ir"]

        tresorerie = round(max(0, benef_apres_is - dividendes_bruts), 2)
        revenu_net = round(max(0, salaire_net - montant_ir + dividendes_nets), 2)

        return {
            "statut"        : "SASU (IS)",
            "regime_fiscal" : "IS",
            "regime_social" : label_rs,
            "eligible"      : True,

            "entreprise": {
                "ca"                    : round(ca, 2),
                "charges_deductibles"   : round(charges_deductibles, 2),
                "abattement_forfaitaire": 0,
                "taux_abattement"       : 0,
                "regime_fiscal"         : "IS (15% ≤ 42 500€ · 25% au-delà)",
                "base_imposable_is"     : benef_imposable_is,
                "impot_societes"        : montant_is,
                "taux_is_effectif"      : is_res["taux_effectif"],
                "reste_apres_impots"    : benef_apres_is,
            },

            "salaire": {
                "applicable"                 : True,
                "mode_ir"                    : False,
                "salaire_net_saisi"          : round(salaire_net, 2),
                "taux_cotisations"           : taux_coti,
                "cotisations"                : cotisations,
                "detail_cotisations"         : detail_rs,
                "salaire_brut"               : salaire_brut,
                "ir_personnel"               : montant_ir,
                "tmi"                        : ir["tmi"],
                "taux_moyen_ir"              : ir["taux_moyen"],
                "salaire_net_apres_ir"       : round(max(0, salaire_net - montant_ir), 2),
                "total_impots_boite_salaire" : cotisations,
            },

            "dividendes": {
                "applicable"             : True,
                "dividendes_bruts"       : round(dividendes_bruts, 2),
                "seuil_tns"              : 0,
                "cotisations_tns_div"    : 0,
                "cotisations_ssi_div"    : 0,
                "ir_pfu_total"           : ft["ir_pfu"],
                "ps_total"               : ft["ps"],
                "montant_flat_tax"       : montant_ft,
                "dividendes_nets"        : dividendes_nets,
                "total_impots_dividendes": montant_ft,
                "detail_flat_tax"        : "Flat tax 31,4% complète (PFU 12,8% + prél. sociaux 17,2% + PS 1,4%) — pas de cotisations sociales en SASU ✅",
            },

            "tresorerie": {
                "applicable"  : True,
                "compte_boite": tresorerie,
                "detail"      : f"Bénéf. IS {benef_imposable_is:,.0f}€ − IS {montant_is:,.0f}€ = {benef_apres_is:,.0f}€ − dividendes {dividendes_bruts:,.0f}€",
            },

            "synthese": {
                "revenu_net_disponible"  : revenu_net,
                "total_impots_et_charges": round(cotisations + montant_is + montant_ft + montant_ir, 2),
                "tmi"                    : ir["tmi"],
                "taux_moyen_ir"          : ir["taux_moyen"],
                "trimestres_retraite"    : trimestres,
            },
        }

    else:  # IR
        benef_avant_coti = round(max(0, ca - charges_deductibles), 2)
        cotisations      = round(benef_avant_coti * taux_coti / (1 + taux_coti), 2)
        benef_imposable  = round(max(0, benef_avant_coti - cotisations), 2)

        pass_trim  = CONFIG["retraite"]["salaire_brut_min_1_trimestre"]
        trimestres = min(4, int(benef_avant_coti / pass_trim)) if benef_avant_coti > 0 else 0

        ir         = calculer_ir(benef_imposable, nb_parts)
        montant_ir = ir["montant_ir"]
        revenu_net = round(max(0, benef_imposable - montant_ir), 2)

        return {
            "statut"        : "SASU (IR)",
            "regime_fiscal" : "IR",
            "regime_social" : label_rs,
            "eligible"      : True,

            "entreprise": {
                "ca"                    : round(ca, 2),
                "charges_deductibles"   : round(charges_deductibles, 2),
                "abattement_forfaitaire": 0,
                "taux_abattement"       : 0,
                "regime_fiscal"         : "IR (barème progressif — tout le bénéfice imposé au dirigeant)",
                "base_imposable_ir"     : benef_imposable,
                "impot_societes"        : 0,
                "taux_is_effectif"      : 0,
                "reste_apres_impots"    : benef_imposable,
            },

            "salaire": {
                "applicable"                 : True,
                "mode_ir"                    : True,
                "remuneration_brute"         : benef_avant_coti,
                "taux_cotisations"           : taux_coti,
                "cotisations"                : cotisations,
                "detail_cotisations"         : detail_rs,
                "remuneration_nette"         : benef_imposable,
                "ir_personnel"               : montant_ir,
                "tmi"                        : ir["tmi"],
                "taux_moyen_ir"              : ir["taux_moyen"],
                "remuneration_nette_apres_ir": revenu_net,
                "total_impots_boite_salaire" : cotisations,
            },

            "dividendes": {
                "applicable": False,
                "raison"    : "Dividendes non disponibles à l'IR",
            },

            "tresorerie": {
                "applicable"  : False,
                "raison"      : "En IR, tout le bénéfice est imposé au dirigeant — pas de trésorerie séparée",
                "compte_boite": 0,
            },

            "synthese": {
                "revenu_net_disponible"  : revenu_net,
                "total_impots_et_charges": round(cotisations + montant_ir, 2),
                "tmi"                    : ir["tmi"],
                "taux_moyen_ir"          : ir["taux_moyen"],
                "trimestres_retraite"    : trimestres,
            },
        }