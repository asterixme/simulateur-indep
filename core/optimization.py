"""
optimization.py — Compare les statuts juridiques et génère une recommandation
"""

from core.income import simuler_micro, simuler_eurl_is, simuler_sasu_is
import json
from pathlib import Path


def _charger_config() -> dict:
    chemin = Path(__file__).parent.parent / "data" / "config.json"
    with open(chemin, "r", encoding="utf-8") as f:
        return json.load(f)


CONFIG = _charger_config()


def optimiser_remuneration_sasu(ca: float, charges: float, nb_parts: float) -> dict:
    """
    Trouve le mix salaire/dividendes optimal pour la SASU.
    Stratégie : salaire min pour 4 trimestres retraite + reste en dividendes.
    """
    cfg = CONFIG["retraite"]
    salaire_brut_min = cfg["salaire_brut_min_4_trimestres"]
    # Salaire net approx = brut / 1.82
    salaire_net_min = salaire_brut_min / 1.82

    # Bénéfice disponible après charges et salaire minimum
    cout_total_salaire_min = salaire_net_min * 1.82
    benefice_dispo = ca - charges - cout_total_salaire_min

    if benefice_dispo <= 0:
        return simuler_sasu_is(ca, charges, salaire_net=max(0, ca - charges) / 1.82, dividendes=0, nb_parts=nb_parts)

    # Distribuer une partie du bénéfice (après IS) en dividendes
    # On garde 30% en trésorerie société pour prudence
    dividendes_potentiels = benefice_dispo * 0.7

    return simuler_sasu_is(
        ca=ca,
        charges_deductibles=charges,
        salaire_net=salaire_net_min,
        dividendes=dividendes_potentiels,
        nb_parts=nb_parts,
    )


def optimiser_remuneration_eurl(ca: float, charges: float, nb_parts: float, capital_social: float) -> dict:
    """
    Trouve le mix rémunération/dividendes optimal pour l'EURL à l'IS.
    Les dividendes au-delà de 10% du capital sont soumis aux cotisations TNS
    → on optimise selon ce seuil.
    """
    seuil_div = capital_social * 0.10
    benefice_brut = ca - charges

    if benefice_brut <= 0:
        return simuler_eurl_is(ca, charges, remuneration_dirigeant=0, dividendes=0, nb_parts=nb_parts, capital_social=capital_social)

    # Stratégie : rémunération TNS + dividendes sous seuil pour minimiser cotisations
    remuneration = benefice_brut * 0.5
    dividendes = min(seuil_div, benefice_brut * 0.3)

    return simuler_eurl_is(
        ca=ca,
        charges_deductibles=charges,
        remuneration_dirigeant=remuneration,
        dividendes=dividendes,
        nb_parts=nb_parts,
        capital_social=capital_social,
    )


def comparer_statuts(
    ca: float,
    type_activite: str,
    charges_reelles: float,
    nb_parts: float = 1.0,
    capital_social: float = 1000,
    situation_are: bool = False,
) -> dict:
    """
    Compare tous les statuts et retourne une recommandation.

    Args:
        ca: chiffre d'affaires annuel HT (€)
        type_activite: 'commerce', 'services_bic' ou 'services_bnc'
        charges_reelles: charges professionnelles réelles annuelles (€)
        nb_parts: quotient familial
        capital_social: capital social envisagé pour EURL/SASU (€)
        situation_are: True si la personne bénéficie de l'ARE (chômage)

    Returns:
        dict avec résultats pour chaque statut + recommandation
    """
    resultats = {}

    # --- Micro-entreprise ---
    resultats["micro"] = simuler_micro(ca, type_activite, nb_parts)

    # --- EURL IS (optimisé) ---
    resultats["eurl"] = optimiser_remuneration_eurl(ca, charges_reelles, nb_parts, capital_social)

    # --- SASU IS (optimisé) ---
    resultats["sasu"] = optimiser_remuneration_sasu(ca, charges_reelles, nb_parts)

    # --- Classement par revenu net disponible ---
    classement = sorted(
        resultats.items(),
        key=lambda x: x[1]["revenu_net_disponible"],
        reverse=True
    )

    meilleur_statut = classement[0][0]
    meilleur_revenu = classement[0][1]["revenu_net_disponible"]

    # --- Génération de la recommandation textuelle ---
    recommandation = _generer_recommandation(
        meilleur_statut=meilleur_statut,
        resultats=resultats,
        ca=ca,
        type_activite=type_activite,
        charges_reelles=charges_reelles,
        situation_are=situation_are,
    )

    return {
        "resultats": resultats,
        "classement": [(s, r["revenu_net_disponible"]) for s, r in classement],
        "meilleur_statut": meilleur_statut,
        "meilleur_revenu_net": meilleur_revenu,
        "recommandation": recommandation,
        "parametres": {
            "ca": ca,
            "type_activite": type_activite,
            "charges_reelles": charges_reelles,
            "nb_parts": nb_parts,
        }
    }


def _generer_recommandation(
    meilleur_statut: str,
    resultats: dict,
    ca: float,
    type_activite: str,
    charges_reelles: float,
    situation_are: bool,
) -> dict:
    """Génère un texte de recommandation contextualisé."""

    cfg_micro = CONFIG["micro_entreprise"]
    plafond_micro = cfg_micro[f"plafond_ca_{type_activite}"]
    abattement = cfg_micro["abattements"][type_activite]
    abattement_montant = ca * abattement

    lignes = []
    avantages = []
    points_attention = []

    # Cas ARE
    if situation_are:
        lignes.append("⚠️ Vous bénéficiez de l'ARE : la SASU sans salaire est souvent la stratégie optimale pour maintenir vos allocations intégralement.")
        avantages.append("SASU sans salaire → ARE maintenue à 100%")
        avantages.append("EURL → cotisations minimales ~1 160€/an même sans rémunération")
        avantages.append("Micro → le CA réduit votre ARE proportionnellement")

    # Dépassement plafond micro
    if ca > plafond_micro:
        lignes.append(f"❌ La micro-entreprise est impossible : votre CA ({ca:,.0f}€) dépasse le plafond de {plafond_micro:,.0f}€.")

    # Comparaison abattement vs charges réelles
    if charges_reelles > abattement_montant and ca <= plafond_micro:
        lignes.append(
            f"📊 Vos charges réelles ({charges_reelles:,.0f}€) dépassent l'abattement forfaitaire micro "
            f"({abattement_montant:,.0f}€ = {abattement*100:.0f}% × {ca:,.0f}€). "
            f"Une société (EURL/SASU) devient plus avantageuse."
        )
    elif ca <= plafond_micro and charges_reelles <= abattement_montant:
        lignes.append(
            f"📊 Vos charges réelles ({charges_reelles:,.0f}€) sont inférieures à l'abattement forfaitaire micro "
            f"({abattement_montant:,.0f}€). La micro-entreprise reste avantageuse fiscalement."
        )

    # Recommandation principale
    labels = {"micro": "Micro-entreprise", "eurl": "EURL (IS)", "sasu": "SASU (IS)"}
    label_meilleur = labels[meilleur_statut]
    ecart_2e = resultats[meilleur_statut]["revenu_net_disponible"] - resultats[list({"micro","eurl","sasu"} - {meilleur_statut})[0]]["revenu_net_disponible"]

    if meilleur_statut == "micro":
        avantages += [
            "Simplicité administrative maximale",
            "Pas de comptabilité complète ni d'expert-comptable obligatoire",
            "Création gratuite et immédiate",
            "Cotisations calculées uniquement si vous encaissez du CA",
        ]
        points_attention += [
            f"Plafond de CA à {plafond_micro:,.0f}€/an",
            "Impossible de déduire vos charges réelles",
            "Pas de dividendes possibles",
        ]

    elif meilleur_statut == "eurl":
        avantages += [
            "Charges réelles déductibles (loyer, matériel, comptable…)",
            "Cotisations TNS moins élevées qu'en SASU (~45% du net vs 82%)",
            "Dividendes possibles (attention au seuil de 10% du capital)",
            "Pas de DSN mensuelle à gérer",
        ]
        points_attention += [
            "Cotisations minimales ~1 160€/an même sans rémunération",
            "Comptabilité complète obligatoire (expert-comptable recommandé)",
            "Les dividendes au-delà de 10% du capital sont soumis aux cotisations TNS",
        ]

    elif meilleur_statut == "sasu":
        avantages += [
            "Dividendes non soumis aux cotisations sociales (flat tax 31,4% uniquement)",
            "Meilleure protection sociale (régime général)",
            "Zéro cotisations si zéro salaire (utile en phase de démarrage ou avec ARE)",
            "Plus de flexibilité pour optimiser salaire/dividendes",
        ]
        points_attention += [
            "Cotisations assimilé salarié élevées (~82% du net) si vous vous versez un salaire",
            "DSN mensuelle obligatoire dès qu'un salaire est versé",
            "Comptabilité complète (expert-comptable recommandé : 1 200-2 500€/an)",
        ]

    return {
        "statut_recommande": label_meilleur,
        "revenu_net_optimal": round(resultats[meilleur_statut]["revenu_net_disponible"], 2),
        "contexte": lignes,
        "avantages": avantages,
        "points_attention": points_attention,
    }