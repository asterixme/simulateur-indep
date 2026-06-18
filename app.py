"""
app.py — Simulateur de statut juridique 2026
Interface Streamlit avec paramétrage IS/IR, salaire et dividendes ajustables en temps réel.
"""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.income import simuler_micro, simuler_eurl, simuler_sasu
from core.optimization import comparer_statuts, optimiser_remuneration_eurl, optimiser_remuneration_sasu
from core.tax import _charger_config

CONFIG = _charger_config()

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Simulateur Statut Juridique 2026",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ Simulateur de statut juridique 2026")
st.caption("Compare Micro-entreprise, EURL et SASU · Barèmes fiscaux et sociaux 2026")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — PARAMÈTRES DE LA SIMULATION
# ─────────────────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.subheader("① Paramètres de la simulation")

    col1, col2, col3 = st.columns(3)

    with col1:
        ca = st.number_input(
            "Chiffre d'affaires annuel HT (€)",
            min_value=0, max_value=2_000_000, value=80_000, step=1_000,
            help="Votre CA prévisionnel ou réel sur 12 mois",
        )
        type_activite = st.selectbox(
            "Type d'activité",
            options=["services_bnc", "services_bic", "commerce"],
            format_func=lambda x: {
                "services_bnc": "Prestations de services (BNC) — libéral, consultant…",
                "services_bic": "Prestations de services (BIC) — artisan, agence…",
                "commerce":     "Commerce / vente de biens",
            }[x],
        )

    with col2:
        charges_reelles = st.number_input(
            "Charges professionnelles réelles (€/an)",
            min_value=0, max_value=500_000, value=5_000, step=500,
            help="Loyer, matériel, logiciels, expert-comptable, déplacements… hors rémunération",
        )
        situation_familiale = st.selectbox(
            "Situation familiale",
            options=[
                "celibataire_sans_enfant", "celibataire_1_enfant", "celibataire_2_enfants", "celibataire_3_enfants",
                "marie_sans_enfant",       "marie_1_enfant",       "marie_2_enfants",       "marie_3_enfants",
            ],
            format_func=lambda x: {
                "celibataire_sans_enfant": "Célibataire — sans enfant",
                "celibataire_1_enfant":    "Célibataire — 1 enfant",
                "celibataire_2_enfants":   "Célibataire — 2 enfants",
                "celibataire_3_enfants":   "Célibataire — 3 enfants",
                "marie_sans_enfant":       "Marié(e)/Pacsé(e) — sans enfant",
                "marie_1_enfant":          "Marié(e)/Pacsé(e) — 1 enfant",
                "marie_2_enfants":         "Marié(e)/Pacsé(e) — 2 enfants",
                "marie_3_enfants":         "Marié(e)/Pacsé(e) — 3 enfants",
            }[x],
        )

    with col3:
        capital_social = st.number_input(
            "Capital social EURL/SASU (€)",
            min_value=1, max_value=100_000, value=1_000, step=100,
            help="Sert au calcul du seuil de dividendes soumis aux cotisations TNS en EURL (10% du capital)",
        )
        situation_are = st.checkbox(
            "Je bénéficie de l'ARE (allocations chômage)",
            value=False,
        )

nb_parts = CONFIG["impot_revenu"]["parts_fiscales"][situation_familiale]
benefice_brut = max(0, ca - charges_reelles)

# ─────────────────────────────────────────────────────────────────────────────
# CALCUL DES OPTIMA PAR DÉFAUT (pour initialiser les sliders)
# ─────────────────────────────────────────────────────────────────────────────
def _valeurs_defaut_eurl_is():
    seuil_div = capital_social * 0.10
    rem = benefice_brut * 0.5
    div = min(seuil_div, benefice_brut * 0.3)
    return round(rem), round(div)

def _valeurs_defaut_sasu_is():
    sal_brut_min = CONFIG["retraite"]["salaire_brut_min_4_trimestres"]
    sal_net_min = round(sal_brut_min / 1.82)
    cout_sal = sal_net_min * 1.82
    dispo = benefice_brut - cout_sal
    div = round(max(0, dispo) * 0.7)
    return sal_net_min, div

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — LES TROIS STATUTS
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
st.subheader("② Résultats par statut — ajustez les paramètres en temps réel")

col_micro, col_eurl, col_sasu = st.columns(3)

# ── MICRO ────────────────────────────────────────────────────────────────────
with col_micro:
    with st.container(border=True):
        st.markdown("### 🟦 Micro-entreprise")
        st.caption("Régime IR uniquement · Pas de dividendes")

        cfg_micro = CONFIG["micro_entreprise"]
        plafond = cfg_micro[f"plafond_ca_{type_activite}"]
        eligible_micro = ca <= plafond

        if not eligible_micro:
            st.error(f"❌ Non éligible — CA ({ca:,.0f}€) > plafond ({plafond:,.0f}€)")
            res_micro = {"revenu_net_disponible": 0, "eligible": False}
        else:
            res_micro = simuler_micro(ca, type_activite, nb_parts)
            st.metric("💰 Revenu net disponible", f"{res_micro['revenu_net_disponible']:,.0f} €/an")
            st.metric("📅 Soit par mois", f"{res_micro['mensuel']['revenu_total_mensuel']:,.0f} €/mois")
            st.divider()
            st.markdown(f"**Régime fiscal** : IR")
            st.markdown(f"**Régime social** : TNS (SSI)")
            abt = cfg_micro['abattements'][type_activite]
            st.markdown(f"**Abattement forfaitaire** : {abt*100:.0f}% → {res_micro['abattement_forfaitaire']:,.0f} €")
            st.markdown(f"**Cotisations sociales** : {res_micro['cotisations_sociales']:,.0f} €")
            st.markdown(f"**Impôt sur le revenu** : {res_micro['impot_revenu']:,.0f} €")
            st.markdown(f"**TMI** : {res_micro['tmi']}%  ·  Taux moyen IR : {res_micro['taux_moyen_ir']}%")
            st.markdown(f"**Dividendes** : ❌ non disponibles")

# ── EURL ─────────────────────────────────────────────────────────────────────
with col_eurl:
    with st.container(border=True):
        st.markdown("### 🟨 EURL")
        st.caption("IS ou IR · TNS (SSI) · Dividendes possibles à l'IS")

        eurl_regime = st.radio(
            "Régime fiscal",
            options=["IS (recommandé si bénéfice > 30k€)", "IR (si faibles revenus)"],
            key="eurl_regime",
            horizontal=True,
        )
        eurl_is = eurl_regime.startswith("IS")

        if eurl_is:
            def_rem_eurl, def_div_eurl = _valeurs_defaut_eurl_is()
            rem_eurl = st.slider(
                "Rémunération nette dirigeant (€/an)",
                min_value=0, max_value=int(benefice_brut) if benefice_brut > 0 else 1,
                value=min(def_rem_eurl, int(benefice_brut)),
                step=500, key="rem_eurl",
                help="Votre salaire net TNS annuel",
            )
            seuil_div_eurl = round(capital_social * 0.10)
            div_max_eurl = max(0, int(benefice_brut - rem_eurl))
            div_eurl = st.slider(
                f"Dividendes bruts (€/an) · Seuil TNS : {seuil_div_eurl:,}€",
                min_value=0, max_value=div_max_eurl,
                value=min(def_div_eurl, div_max_eurl),
                step=500, key="div_eurl",
                help=f"Au-delà de {seuil_div_eurl:,}€ (10% du capital), les dividendes supportent des cotisations TNS",
            )
            res_eurl = simuler_eurl(ca, charges_reelles, rem_eurl, div_eurl, nb_parts, capital_social, "IS")
        else:
            rem_eurl_ir = st.slider(
                "Rémunération nette dirigeant (€/an)",
                min_value=0, max_value=int(benefice_brut) if benefice_brut > 0 else 1,
                value=min(int(benefice_brut * 0.7), int(benefice_brut)),
                step=500, key="rem_eurl_ir",
            )
            res_eurl = simuler_eurl(ca, charges_reelles, rem_eurl_ir, 0, nb_parts, capital_social, "IR")

        st.divider()
        st.metric("💰 Revenu net disponible", f"{res_eurl['revenu_net_disponible']:,.0f} €/an")
        st.metric("📅 Soit par mois", f"{res_eurl['mensuel']['revenu_total_mensuel']:,.0f} €/mois")
        st.divider()
        st.markdown(f"**Régime fiscal** : {res_eurl['regime_fiscal']}")
        st.markdown(f"**Régime social** : {res_eurl['regime_social']}")
        st.markdown(f"**Cotisations TNS (rémun.)** : {res_eurl['cotisations_tns_remuneration']:,.0f} €")
        if eurl_is:
            st.markdown(f"**Cotisations TNS (divid.)** : {res_eurl['cotisations_tns_dividendes']:,.0f} €")
            st.markdown(f"**Bénéfice imposable IS** : {res_eurl['benefice_imposable']:,.0f} €")
            st.markdown(f"**Impôt sur les sociétés** : {res_eurl['impot_societes']:,.0f} €")
            st.markdown(f"**Flat tax dividendes** : {res_eurl['flat_tax_dividendes']:,.0f} €")
            st.markdown(f"**Dividendes nets** : {res_eurl['dividendes_nets']:,.0f} €")
        st.markdown(f"**Impôt sur le revenu** : {res_eurl['impot_revenu']:,.0f} €")
        st.markdown(f"**TMI** : {res_eurl['tmi']}%  ·  Taux moyen IR : {res_eurl['taux_moyen_ir']}%")

# ── SASU ─────────────────────────────────────────────────────────────────────
with col_sasu:
    with st.container(border=True):
        st.markdown("### 🟩 SASU")
        st.caption("IS par défaut · Assimilé salarié · Dividendes sans cotisations sociales")

        sasu_regime = st.radio(
            "Régime fiscal",
            options=["IS (par défaut)", "IR (option 5 premiers exercices)"],
            key="sasu_regime",
            horizontal=True,
        )
        sasu_is = sasu_regime.startswith("IS")

        def_sal_sasu, def_div_sasu = _valeurs_defaut_sasu_is()

        if sasu_is:
            sal_sasu = st.slider(
                "Salaire net président (€/an)",
                min_value=0, max_value=int(benefice_brut) if benefice_brut > 0 else 1,
                value=min(def_sal_sasu, int(benefice_brut)),
                step=500, key="sal_sasu",
                help="Minimum 7 212€ brut/an pour valider 4 trimestres retraite",
            )
            cout_sal_sasu = sal_sasu * 1.82
            div_max_sasu = max(0, int(benefice_brut - cout_sal_sasu))
            div_sasu = st.slider(
                "Dividendes bruts (€/an)",
                min_value=0, max_value=div_max_sasu,
                value=min(def_div_sasu, div_max_sasu),
                step=500, key="div_sasu",
                help="En SASU, les dividendes ne supportent pas de cotisations sociales (flat tax 31,4% uniquement)",
            )
            res_sasu = simuler_sasu(ca, charges_reelles, sal_sasu, div_sasu, nb_parts, "IS")
        else:
            sal_sasu_ir = st.slider(
                "Salaire net président (€/an)",
                min_value=0, max_value=int(benefice_brut) if benefice_brut > 0 else 1,
                value=min(def_sal_sasu, int(benefice_brut)),
                step=500, key="sal_sasu_ir",
            )
            res_sasu = simuler_sasu(ca, charges_reelles, sal_sasu_ir, 0, nb_parts, "IR")

        st.divider()
        st.metric("💰 Revenu net disponible", f"{res_sasu['revenu_net_disponible']:,.0f} €/an")
        st.metric("📅 Soit par mois", f"{res_sasu['mensuel']['revenu_total_mensuel']:,.0f} €/mois")
        st.divider()
        st.markdown(f"**Régime fiscal** : {res_sasu['regime_fiscal']}")
        st.markdown(f"**Régime social** : {res_sasu['regime_social']}")
        st.markdown(f"**Cotisations assimilé salarié** : {res_sasu['cotisations_sociales']:,.0f} €")
        if sasu_is:
            st.markdown(f"**Bénéfice imposable IS** : {res_sasu['benefice_imposable']:,.0f} €")
            st.markdown(f"**Impôt sur les sociétés** : {res_sasu['impot_societes']:,.0f} €")
            st.markdown(f"**Flat tax dividendes** : {res_sasu['flat_tax_dividendes']:,.0f} €")
            st.markdown(f"**Dividendes nets** : {res_sasu['dividendes_nets']:,.0f} €")
            st.markdown(f"**Trimestres retraite** : {res_sasu.get('trimestres_retraite_valides', 0)}/4 validés")
        st.markdown(f"**Impôt sur le revenu** : {res_sasu['impot_revenu']:,.0f} €")
        st.markdown(f"**TMI** : {res_sasu['tmi']}%  ·  Taux moyen IR : {res_sasu['taux_moyen_ir']}%")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — RECOMMANDATION FINALE
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
st.subheader("③ Recommandation et synthèse")

# Construire le classement à partir des résultats actuels (avec les sliders)
resultats_courants = {
    "micro": res_micro,
    "eurl":  res_eurl,
    "sasu":  res_sasu,
}

classement = sorted(
    [(k, v) for k, v in resultats_courants.items() if v.get("eligible", True)],
    key=lambda x: x[1]["revenu_net_disponible"],
    reverse=True,
)

labels = {"micro": "Micro-entreprise", "eurl": f"EURL ({res_eurl['regime_fiscal']})", "sasu": f"SASU ({res_sasu['regime_fiscal']})"}
medailles = ["🥇", "🥈", "🥉"]

# Bannière recommandation
if classement:
    meilleur_k, meilleur_v = classement[0]
    st.success(f"**{medailles[0]} Statut optimal avec ces paramètres : {labels[meilleur_k]}** — {meilleur_v['revenu_net_disponible']:,.0f} €/an net disponible")

    if situation_are:
        st.warning("⚠️ **Avec l'ARE :** la SASU sans salaire (0€) est souvent la meilleure stratégie pour maintenir vos allocations intégralement. En EURL, des cotisations minimales (~1 160€/an) sont dues même sans rémunération.")

# Tableau de synthèse comparatif
st.markdown("#### Tableau comparatif avec vos paramètres")

colonnes = ["Critère"] + [labels[k] for k, _ in classement]
lignes = []

def fmt(v, suffix="€"):
    if isinstance(v, (int, float)):
        return f"{v:,.0f} {suffix}" if suffix else f"{v:,.0f}"
    return str(v)

for k, v in classement:
    pass  # just iterate to build rows

rows_data = {
    "💰 Revenu net disponible / an":   {k: fmt(v["revenu_net_disponible"]) for k,v in classement},
    "📅 Revenu net disponible / mois": {k: fmt(v["mensuel"]["revenu_total_mensuel"]) for k,v in classement},
    "🏛️ Régime fiscal":               {k: v["regime_fiscal"] for k,v in classement},
    "👷 Régime social":               {k: v["regime_social"] for k,v in classement},
    "📊 Cotisations sociales":         {k: fmt(v["cotisations_sociales"]) for k,v in classement},
    "💼 Impôt sur le revenu (IR)":    {k: fmt(v["impot_revenu"]) for k,v in classement},
    "🏢 Impôt sur les sociétés (IS)": {k: fmt(v["impot_societes"]) for k,v in classement},
    "📈 Flat tax dividendes":          {k: fmt(v["flat_tax_dividendes"]) for k,v in classement},
    "💸 Dividendes nets":              {k: fmt(v["dividendes_nets"]) for k,v in classement},
    "📉 TMI":                          {k: f"{v['tmi']}%" for k,v in classement},
    "📉 Taux moyen IR":                {k: f"{v['taux_moyen_ir']}%" for k,v in classement},
}

import pandas as pd
table_rows = []
for critere, vals in rows_data.items():
    row = {"Critère": critere}
    for k, v in classement:
        row[labels[k]] = vals.get(k, "—")
    table_rows.append(row)

df = pd.DataFrame(table_rows).set_index("Critère")
st.dataframe(df, use_container_width=True)

# Détail mensuel
st.markdown("#### Détail mensuel")
cols_mensuel = st.columns(len(classement))
for i, (k, v) in enumerate(classement):
    with cols_mensuel[i]:
        st.markdown(f"**{medailles[i]} {labels[k]}**")
        m = v["mensuel"]
        st.markdown(f"- Salaire / revenu net : **{m['salaire_net_mensuel']:,.0f} €**")
        st.markdown(f"- Cotisations : {m['cotisations_mensuelles']:,.0f} €")
        st.markdown(f"- IR mensuel (estimé) : {m['impot_revenu_mensuel']:,.0f} €")
        if m.get("dividendes_nets_mensuel", 0) > 0:
            st.markdown(f"- Dividendes nets : {m['dividendes_nets_mensuel']:,.0f} €")
        st.markdown(f"- **Total en poche : {m['revenu_total_mensuel']:,.0f} €/mois**")

# Points d'attention contextuels
st.markdown("#### Points d'attention")
cfg_micro = CONFIG["micro_entreprise"]
abattement_montant = ca * cfg_micro["abattements"][type_activite]

col_a, col_b = st.columns(2)
with col_a:
    if ca > cfg_micro[f"plafond_ca_{type_activite}"]:
        st.error(f"❌ **Micro impossible** : CA {ca:,.0f}€ > plafond {cfg_micro[f'plafond_ca_{type_activite}']:,.0f}€")
    if charges_reelles > abattement_montant:
        st.warning(f"📊 Vos charges réelles ({charges_reelles:,.0f}€) dépassent l'abattement micro ({abattement_montant:,.0f}€) → une société est fiscalement plus intéressante")
    else:
        st.info(f"📊 Abattement micro ({abattement_montant:,.0f}€) > vos charges réelles ({charges_reelles:,.0f}€) → micro avantageuse sur ce critère")

with col_b:
    sal_brut_sasu = res_sasu.get("salaire_brut_annuel", 0)
    trim_min = CONFIG["retraite"]["salaire_brut_min_4_trimestres"]
    if sal_brut_sasu < trim_min and res_sasu["regime_fiscal"] == "IS":
        st.warning(f"⚠️ **Retraite SASU** : salaire brut ({sal_brut_sasu:,.0f}€) < {trim_min:,.0f}€ → moins de 4 trimestres validés")
    seuil_div_eurl = round(capital_social * 0.10)
    if res_eurl.get("dividendes_bruts", 0) > seuil_div_eurl:
        st.warning(f"⚠️ **EURL dividendes** : {res_eurl['dividendes_bruts']:,.0f}€ versés > seuil TNS ({seuil_div_eurl:,}€) → cotisations supplémentaires appliquées")

# Disclaimer
st.divider()
st.caption(
    "⚠️ Simulation indicative basée sur les barèmes 2026. Ne constitue pas un conseil fiscal ou juridique. "
    "Consultez un expert-comptable pour votre situation personnelle."
)