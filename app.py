"""
app.py — Interface Streamlit du simulateur de statut juridique 2026
"""

import streamlit as st
import sys
from pathlib import Path

# Permet d'importer les modules core/ depuis la racine du projet
sys.path.insert(0, str(Path(__file__).parent))

from core.optimization import comparer_statuts

# ─────────────────────────────────────────────
# CONFIG PAGE
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Simulateur Statut Juridique 2026",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ Simulateur de statut juridique 2026")
st.caption("Compare Micro-entreprise, EURL et SASU · Barèmes fiscaux et sociaux 2026")

st.divider()

# ─────────────────────────────────────────────
# FORMULAIRE
# ─────────────────────────────────────────────
with st.form("formulaire_simulation"):
    st.subheader("📋 Votre situation")

    col1, col2 = st.columns(2)

    with col1:
        ca = st.number_input(
            "Chiffre d'affaires annuel HT (€)",
            min_value=0,
            max_value=2_000_000,
            value=80_000,
            step=1_000,
            help="Votre CA prévisionnel ou réel sur 12 mois",
        )

        type_activite = st.selectbox(
            "Type d'activité",
            options=["services_bnc", "services_bic", "commerce"],
            format_func=lambda x: {
                "services_bnc": "Prestations de services (BNC) — consultant, libéral, coach…",
                "services_bic": "Prestations de services (BIC) — artisan, agence…",
                "commerce":     "Commerce / vente de biens",
            }[x],
            help="Détermine l'abattement forfaitaire en micro et les plafonds de CA",
        )

        charges_reelles = st.number_input(
            "Charges professionnelles réelles annuelles (€)",
            min_value=0,
            max_value=500_000,
            value=5_000,
            step=500,
            help="Loyer, matériel, logiciels, expert-comptable, déplacements… (hors votre rémunération)",
        )

    with col2:
        situation_familiale = st.selectbox(
            "Situation familiale",
            options=[
                "celibataire_sans_enfant",
                "celibataire_1_enfant",
                "celibataire_2_enfants",
                "celibataire_3_enfants",
                "marie_sans_enfant",
                "marie_1_enfant",
                "marie_2_enfants",
                "marie_3_enfants",
            ],
            format_func=lambda x: {
                "celibataire_sans_enfant":  "Célibataire / seul(e) — sans enfant",
                "celibataire_1_enfant":     "Célibataire — 1 enfant à charge",
                "celibataire_2_enfants":    "Célibataire — 2 enfants à charge",
                "celibataire_3_enfants":    "Célibataire — 3 enfants à charge",
                "marie_sans_enfant":        "Marié(e) / Pacsé(e) — sans enfant",
                "marie_1_enfant":           "Marié(e) / Pacsé(e) — 1 enfant",
                "marie_2_enfants":          "Marié(e) / Pacsé(e) — 2 enfants",
                "marie_3_enfants":          "Marié(e) / Pacsé(e) — 3 enfants",
            }[x],
        )

        capital_social = st.number_input(
            "Capital social envisagé pour EURL/SASU (€)",
            min_value=1,
            max_value=100_000,
            value=1_000,
            step=100,
            help="Sert au calcul du seuil de dividendes soumis aux cotisations TNS en EURL (10% du capital)",
        )

        situation_are = st.checkbox(
            "Je bénéficie actuellement de l'ARE (allocations chômage)",
            value=False,
            help="Active des recommandations spécifiques pour maintenir vos allocations",
        )

    submitted = st.form_submit_button("🔍 Lancer la simulation", use_container_width=True, type="primary")

# ─────────────────────────────────────────────
# RÉSULTATS
# ─────────────────────────────────────────────
if submitted:
    from core.tax import _charger_config
    config = _charger_config()
    nb_parts = config["impot_revenu"]["parts_fiscales"][situation_familiale]

    with st.spinner("Calcul en cours…"):
        try:
            resultats = comparer_statuts(
                ca=ca,
                type_activite=type_activite,
                charges_reelles=charges_reelles,
                nb_parts=nb_parts,
                capital_social=capital_social,
                situation_are=situation_are,
            )
        except Exception as e:
            st.error(f"Erreur lors du calcul : {e}")
            st.stop()

    reco = resultats["recommandation"]

    # ── Recommandation principale ──
    st.divider()
    st.subheader("🏆 Recommandation")

    col_reco, col_gain = st.columns([2, 1])
    with col_reco:
        st.success(f"**Statut recommandé : {reco['statut_recommande']}**")
        for ligne in reco["contexte"]:
            st.info(ligne)

    with col_gain:
        st.metric(
            label="Revenu net disponible estimé",
            value=f"{reco['revenu_net_optimal']:,.0f} €/an",
        )

    col_av, col_att = st.columns(2)
    with col_av:
        st.markdown("**✅ Avantages**")
        for av in reco["avantages"]:
            st.markdown(f"- {av}")
    with col_att:
        st.markdown("**⚠️ Points d'attention**")
        for pt in reco["points_attention"]:
            st.markdown(f"- {pt}")

    # ── Comparaison des 3 statuts ──
    st.divider()
    st.subheader("📊 Comparaison des 3 statuts")

    labels = {"micro": "Micro-entreprise", "eurl": "EURL (IS)", "sasu": "SASU (IS)"}
    cols = st.columns(3)

    for i, (statut, rev_net) in enumerate(resultats["classement"]):
        res = resultats["resultats"][statut]
        is_best = (i == 0)
        with cols[i]:
            medaille = ["🥇", "🥈", "🥉"][i]
            st.markdown(f"### {medaille} {labels[statut]}")

            if not res.get("eligible", True):
                st.error("❌ Non éligible (plafond CA dépassé)")
            else:
                st.metric("Revenu net disponible", f"{res['revenu_net_disponible']:,.0f} €")

            st.markdown("---")
            st.markdown(f"**Cotisations sociales** : {res['cotisations_sociales']:,.0f} €")
            st.markdown(f"**Impôt sur le revenu** : {res['impot_revenu']:,.0f} €")
            st.markdown(f"**Impôt sur les sociétés** : {res['impot_societes']:,.0f} €")
            if res.get("flat_tax_dividendes", 0) > 0:
                st.markdown(f"**Flat tax dividendes** : {res['flat_tax_dividendes']:,.0f} €")
            st.markdown(f"**TMI** : {res['tmi']} %")
            st.markdown(f"**Régime social** : {res['regime_social']}")
            st.markdown(f"**Régime fiscal** : {res['regime_fiscal']}")

    # ── Détail avancé ──
    with st.expander("🔬 Voir le détail complet de chaque calcul"):
        for statut, res in resultats["resultats"].items():
            st.markdown(f"#### {labels[statut]}")
            st.json(res)

    # ── Avertissement légal ──
    st.divider()
    st.caption(
        "⚠️ **Avertissement** : cette simulation est fournie à titre indicatif, "
        "basée sur les barèmes fiscaux et sociaux 2026. Elle ne constitue pas un conseil juridique ou fiscal. "
        "Pour votre situation réelle, consultez un expert-comptable."
    )