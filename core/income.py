"""
income.py — Calcul détaillé par statut juridique — Barèmes 2026
Chaque fonction retourne un dict structuré en 4 groupes :
  - entreprise   : CA, régime, IS
  - salaire      : brut, cotisations, net, IR personnel
  - dividendes   : bruts, flat tax, nets  (IS uniquement)
  - tresorerie   : ce qui reste dans la boîte après tout
"""

import json
from pathlib import Path
from core.tax import calculer_ir, calculer_is, calculer_flat_tax

def _charger_config() -> dict:
    chemin = Path(__file__).parent.parent / "data" / "config.json"
    with open(chemin, "r", encoding="utf-8") as f:
        return json.load(f)

CONFIG = _charger_config()


# ─────────────────────────────────────────────────────────────────────────────
# MICRO-ENTREPRISE
# ─────────────────────────────────────────────────────────────────────────────
def simuler_micro(ca: float, type_activite: str, nb_parts: float = 1.0) -> dict:
    cfg   = CONFIG["micro_entreprise"]
    plafond    = cfg[f"plafond_ca_{type_activite}"]
    taux_abt   = cfg["abattements"][type_activite]
    taux_coti  = cfg["taux_cotisations_sur_ca"][type_activite]

    abattement      = round(ca * taux_abt, 2)
    cotisations     = round(ca * taux_coti, 2)
    revenu_imposable = round(ca * (1 - taux_abt), 2)

    ir = calculer_ir(revenu_imposable, nb_parts)
    montant_ir = ir["montant_ir"]

    # En micro : pas de société séparée → pas d'IS, pas de dividendes, pas de trésorerie
    revenu_net = round(max(0, ca - cotisations - montant_ir), 2)

    return {
        "statut"        : "Micro-entreprise",
        "regime_fiscal" : "IR",
        "regime_social" : "TNS (SSI)",
        "eligible"      : ca <= plafond,
        "plafond_ca"    : plafond,

        # ── Groupe Entreprise ──────────────────────────────────────────────
        "entreprise": {
            "ca"                   : round(ca, 2),
            "abattement_forfaitaire": abattement,
            "taux_abattement"       : taux_abt,
            "charges_deductibles"  : 0,
            "regime_fiscal"        : "IR (barème progressif)",
            "base_imposable_ir"    : revenu_imposable,
            "impot_societes"       : 0,
            "taux_is_effectif"     : 0,
            "reste_apres_impots"   : revenu_imposable,   # pas d'IS, tout va au dirigeant
        },

        # ── Groupe Salaire / Rémunération ─────────────────────────────────
        "salaire": {
            "applicable"              : True,
            "mode_ir"                 : True,   # pas de salaire distinct en micro
            "remuneration_brute"      : round(ca - cotisations, 2),
            "taux_cotisations"        : taux_coti,
            "cotisations"             : cotisations,
            "detail_cotisations"      : f"Cotisations TNS sur CA ({taux_coti*100:.1f}% × CA)",
            "remuneration_nette"      : round(ca - cotisations, 2),
            "ir_personnel"            : montant_ir,
            "tmi"                     : ir["tmi"],
            "taux_moyen_ir"           : ir["taux_moyen"],
            "remuneration_nette_apres_ir": revenu_net,
            "total_impots_boite_salaire": 0,   # pas de charges patronales distinctes
        },

        # ── Groupe Dividendes ─────────────────────────────────────────────
        "dividendes": {
            "applicable": False,
            "raison"    : "Dividendes impossibles en micro-entreprise",
        },

        # ── Groupe Trésorerie ─────────────────────────────────────────────
        "tresorerie": {
            "applicable"     : False,
            "raison"         : "Pas de société distincte en micro-entreprise",
            "compte_boite"   : 0,
        },

        # ── Synthèse ──────────────────────────────────────────────────────
        "synthese": {
            "revenu_net_disponible" : revenu_net,
            "total_impots_et_charges": round(cotisations + montant_ir, 2),
            "tmi"                   : ir["tmi"],
            "taux_moyen_ir"         : ir["taux_moyen"],
            "trimestres_retraite"   : None,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# EURL
# ─────────────────────────────────────────────────────────────────────────────
def simuler_eurl(
    ca: float,
    charges_deductibles: float,
    remuneration_net: float,      # salaire net souhaité (IS) ou ignoré (IR)
    dividendes_bruts: float,
    nb_parts: float       = 1.0,
    capital_social: float = 1000,
    regime_fiscal: str    = "IS",
) -> dict:
    cfg_tns     = CONFIG["cotisations_tns"]
    taux_cout   = cfg_tns["cout_total_pour_1000_net"] / 1000   # ex: 1.45
    taux_coti   = cfg_tns["taux_global_sur_net"]               # ex: 0.45

    if regime_fiscal == "IS":
        # ── Cotisations sur salaire ──────────────────────────────────────
        cotisations_sal = round(remuneration_net * (taux_cout - 1), 2)
        salaire_brut    = round(remuneration_net + cotisations_sal, 2)

        # ── IS : calculé sur le bénéfice AVANT distribution de dividendes ─
        # Les cotisations TNS sur dividendes ne sont PAS déduites du bénéfice IS
        # (elles sont dues par le dirigeant sur les dividendes reçus, pas par la société)
        benef_imposable_is = round(max(0, ca - charges_deductibles - salaire_brut), 2)
        is_res             = calculer_is(benef_imposable_is)
        montant_is         = is_res["montant_is"]

        # ── Bénéfice distribuable = bénéfice après IS ───────────────────
        benef_apres_is     = round(max(0, benef_imposable_is - montant_is), 2)
        # Les dividendes ne peuvent pas dépasser le bénéfice après IS
        dividendes_bruts   = round(min(dividendes_bruts, benef_apres_is), 2)

        # ── Cotisations TNS sur dividendes (dues par le dirigeant) ───────
        # Calculées APRÈS avoir plafonné les dividendes au bénéfice après IS
        seuil_div_tns      = round(capital_social * cfg_tns["seuil_dividendes_soumis_cotisations_pct"], 2)
        div_soumis_tns     = round(max(0, dividendes_bruts - seuil_div_tns), 2)
        cotisations_div    = round(div_soumis_tns * (taux_cout - 1), 2)
        total_cotisations  = round(cotisations_sal + cotisations_div, 2)

        # ── Flat tax dividendes ──────────────────────────────────────────
        ft                 = calculer_flat_tax(dividendes_bruts)
        montant_ft         = ft["montant_flat_tax"]
        dividendes_nets    = ft["dividendes_nets"]
        taux_ft            = CONFIG["flat_tax"]["taux_global"]

        # ── IR personnel sur salaire uniquement ──────────────────────────
        ir                 = calculer_ir(remuneration_net, nb_parts)
        montant_ir         = ir["montant_ir"]

        # ── Trésorerie = bénéfice après IS − dividendes distribués ───────
        tresorerie         = round(max(0, benef_apres_is - dividendes_bruts), 2)

        # ── Revenu net perso (salaire net après IR + dividendes nets − coti TNS div) ─
        revenu_net         = round(max(0, remuneration_net - montant_ir + dividendes_nets - cotisations_div), 2)

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
                "applicable"               : True,
                "mode_ir"                  : False,
                "salaire_net_saisi"        : round(remuneration_net, 2),
                "taux_cotisations"         : taux_coti,
                "cotisations"              : cotisations_sal,
                "detail_cotisations"       : f"Cotisations TNS ({taux_coti*100:.0f}% du net)",
                "salaire_brut"             : salaire_brut,
                "ir_personnel"             : montant_ir,
                "tmi"                      : ir["tmi"],
                "taux_moyen_ir"            : ir["taux_moyen"],
                "salaire_net_apres_ir"     : round(max(0, remuneration_net - montant_ir), 2),
                "total_impots_boite_salaire": cotisations_sal,   # charges portées par la boîte
            },

            "dividendes": {
                "applicable"           : True,
                "dividendes_bruts"     : round(dividendes_bruts, 2),
                "seuil_tns"            : seuil_div_tns,
                "cotisations_tns_div"  : cotisations_div,
                "detail_coti_div"      : f"Cotisations TNS sur part > {seuil_div_tns:,.0f}€ ({taux_coti*100:.0f}% du net)",
                "taux_flat_tax"        : taux_ft,
                "montant_flat_tax"     : montant_ft,
                "detail_flat_tax"      : f"Flat tax {taux_ft*100:.1f}% (PFU 12,8% + prél. sociaux 17,2% + PS 1,4%)",
                "dividendes_nets"      : dividendes_nets,
                "total_impots_dividendes": round(montant_ft + cotisations_div, 2),
            },

            "tresorerie": {
                "applicable"   : True,
                "compte_boite" : tresorerie,
                "detail"       : f"Bénéfice imposable IS : {benef_imposable_is:,.0f}€ − IS {montant_is:,.0f}€ = {benef_apres_is:,.0f}€ après IS − dividendes {dividendes_bruts:,.0f}€ distribués",
            },

            "synthese": {
                "revenu_net_disponible"  : revenu_net,
                "total_impots_et_charges": round(total_cotisations + montant_is + montant_ft + montant_ir, 2),
                "tmi"                    : ir["tmi"],
                "taux_moyen_ir"          : ir["taux_moyen"],
                "trimestres_retraite"    : None,
            },
        }

    else:  # IR
        # En EURL à l'IR : tout le bénéfice (CA - charges - cotisations) est imposé à l'IR
        # Les cotisations sont calculées sur le bénéfice (base TNS)
        benef_avant_coti   = round(max(0, ca - charges_deductibles), 2)
        # Approx cotisations : taux_coti × bénéfice avant cotisations / (1 + taux_coti)
        cotisations_sal    = round(benef_avant_coti * taux_coti / (1 + taux_coti), 2)
        benef_imposable    = round(max(0, benef_avant_coti - cotisations_sal), 2)

        ir                 = calculer_ir(benef_imposable, nb_parts)
        montant_ir         = ir["montant_ir"]
        revenu_net         = round(max(0, benef_imposable - montant_ir), 2)

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
                "applicable"               : True,
                "mode_ir"                  : True,
                "remuneration_brute"       : benef_avant_coti,
                "taux_cotisations"         : taux_coti,
                "cotisations"              : cotisations_sal,
                "detail_cotisations"       : f"Cotisations TNS (~{taux_coti*100:.0f}% du bénéfice)",
                "remuneration_nette"       : benef_imposable,
                "ir_personnel"             : montant_ir,
                "tmi"                      : ir["tmi"],
                "taux_moyen_ir"            : ir["taux_moyen"],
                "remuneration_nette_apres_ir": revenu_net,
                "total_impots_boite_salaire": cotisations_sal,
            },

            "dividendes": {
                "applicable": False,
                "raison"    : "Dividendes non disponibles à l'IR",
            },

            "tresorerie": {
                "applicable"   : False,
                "raison"       : "En IR, pas de bénéfice stocké en société — tout est imposé au dirigeant",
                "compte_boite" : 0,
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
# SASU
# ─────────────────────────────────────────────────────────────────────────────
def simuler_sasu(
    ca: float,
    charges_deductibles: float,
    salaire_net: float,
    dividendes_bruts: float,
    nb_parts: float      = 1.0,
    regime_fiscal: str   = "IS",
    regime_social: str   = "assimile_salarie",
) -> dict:
    if regime_social == "tns":
        cfg_rs    = CONFIG["cotisations_tns"]
        label_rs  = "TNS (SSI)"
        detail_rs = f"Cotisations TNS ({cfg_rs['taux_global_sur_net']*100:.0f}% du net)"
    else:
        cfg_rs    = CONFIG["cotisations_assimile_salarie"]
        label_rs  = "Assimilé salarié (Régime général)"
        detail_rs = f"Charges sociales assimilé salarié ({cfg_rs['taux_global_sur_net']*100:.0f}% du net)"

    taux_cout  = cfg_rs["cout_total_pour_1000_net"] / 1000
    taux_coti  = cfg_rs["taux_global_sur_net"]

    if regime_fiscal == "IS":
        cotisations   = round(salaire_net * (taux_cout - 1), 2)
        salaire_brut  = round(salaire_net + cotisations, 2)

        # Trimestres retraite
        pass_trim    = CONFIG["retraite"]["salaire_brut_min_1_trimestre"]
        trimestres   = min(4, int(salaire_brut / pass_trim)) if salaire_brut > 0 else 0

        # IS : calculé sur le bénéfice AVANT distribution de dividendes
        benef_imposable_is = round(max(0, ca - charges_deductibles - salaire_brut), 2)
        is_res             = calculer_is(benef_imposable_is)
        montant_is         = is_res["montant_is"]

        # Bénéfice distribuable = bénéfice après IS
        benef_apres_is     = round(max(0, benef_imposable_is - montant_is), 2)
        # Les dividendes ne peuvent pas dépasser le bénéfice après IS
        dividendes_bruts   = round(min(dividendes_bruts, benef_apres_is), 2)

        # Flat tax dividendes (pas de cotisations sociales sur dividendes en SASU ✅)
        ft                 = calculer_flat_tax(dividendes_bruts)
        montant_ft         = ft["montant_flat_tax"]
        dividendes_nets    = ft["dividendes_nets"]
        taux_ft            = CONFIG["flat_tax"]["taux_global"]

        # IR personnel sur salaire seul
        ir                 = calculer_ir(salaire_net, nb_parts)
        montant_ir         = ir["montant_ir"]

        # Trésorerie = bénéfice après IS − dividendes distribués
        tresorerie         = round(max(0, benef_apres_is - dividendes_bruts), 2)
        revenu_net         = round(max(0, salaire_net - montant_ir + dividendes_nets), 2)

        return {
            "statut"        : "SASU (IS)",
            "regime_fiscal" : "IS",
            "regime_social" : label_rs,
            "regime_social_key": regime_social,
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
                "applicable"               : True,
                "mode_ir"                  : False,
                "salaire_net_saisi"        : round(salaire_net, 2),
                "taux_cotisations"         : taux_coti,
                "cotisations"              : cotisations,
                "detail_cotisations"       : detail_rs,
                "salaire_brut"             : salaire_brut,
                "ir_personnel"             : montant_ir,
                "tmi"                      : ir["tmi"],
                "taux_moyen_ir"            : ir["taux_moyen"],
                "salaire_net_apres_ir"     : round(max(0, salaire_net - montant_ir), 2),
                "total_impots_boite_salaire": cotisations,
            },

            "dividendes": {
                "applicable"             : True,
                "dividendes_bruts"       : round(dividendes_bruts, 2),
                "seuil_tns"              : 0,
                "cotisations_tns_div"    : 0,
                "detail_coti_div"        : "Pas de cotisations sociales sur dividendes en SASU ✅",
                "taux_flat_tax"          : taux_ft,
                "montant_flat_tax"       : montant_ft,
                "detail_flat_tax"        : f"Flat tax {taux_ft*100:.1f}% (PFU 12,8% + prél. sociaux 17,2% + PS 1,4%)",
                "dividendes_nets"        : dividendes_nets,
                "total_impots_dividendes": montant_ft,
            },

            "tresorerie": {
                "applicable"   : True,
                "compte_boite" : tresorerie,
                "detail"       : f"Bénéfice imposable {benef_imposable_is:,.0f}€ − IS {montant_is:,.0f}€ = {benef_apres_is:,.0f}€ après IS − dividendes {dividendes_bruts:,.0f}€ distribués",
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
            "regime_social_key": regime_social,
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
                "applicable"               : True,
                "mode_ir"                  : True,
                "remuneration_brute"       : benef_avant_coti,
                "taux_cotisations"         : taux_coti,
                "cotisations"              : cotisations,
                "detail_cotisations"       : detail_rs,
                "remuneration_nette"       : benef_imposable,
                "ir_personnel"             : montant_ir,
                "tmi"                      : ir["tmi"],
                "taux_moyen_ir"            : ir["taux_moyen"],
                "remuneration_nette_apres_ir": revenu_net,
                "total_impots_boite_salaire": cotisations,
            },

            "dividendes": {
                "applicable": False,
                "raison"    : "Dividendes non disponibles à l'IR",
            },

            "tresorerie": {
                "applicable"   : False,
                "raison"       : "En IR, pas de bénéfice stocké en société — tout est imposé au dirigeant",
                "compte_boite" : 0,
            },

            "synthese": {
                "revenu_net_disponible"  : revenu_net,
                "total_impots_et_charges": round(cotisations + montant_ir, 2),
                "tmi"                    : ir["tmi"],
                "taux_moyen_ir"          : ir["taux_moyen"],
                "trimestres_retraite"    : trimestres,
            },
        }