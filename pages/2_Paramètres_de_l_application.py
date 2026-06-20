"""
pages/2_Paramètres_de_l_application.py — Visualisation de tous les barèmes 2026
"""
import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.tax import _charger_config
import pandas as pd

CONFIG = _charger_config()

st.set_page_config(page_title="Paramètres 2026", page_icon="⚙️", layout="wide")
st.title("⚙️ Paramètres de l'application — Barèmes 2026")
st.caption("Tous les taux et seuils utilisés dans les calculs. Modifiez le fichier `data/config.json` pour les mettre à jour.")

# ── 1. Impôt sur le revenu ───────────────────────────────────────────────────
st.header("1. Impôt sur le revenu (IR) — Barème progressif 2026")
st.markdown("L'IR est calculé par tranches, appliquées au **revenu par part fiscale** (quotient familial).")

tranches = CONFIG["impot_revenu"]["tranches"]
rows_ir = []
prev = 0
for t in tranches:
    borne = t["jusqu_a"]
    label_borne = f"{borne:,.0f} €" if borne else "Au-delà"
    rows_ir.append({
        "De": f"{prev:,.0f} €",
        "Jusqu'à": label_borne,
        "Taux": f"{t['taux']*100:.0f} %",
    })
    if borne:
        prev = borne
st.dataframe(pd.DataFrame(rows_ir), use_container_width=True, hide_index=True)

st.markdown("**Quotient familial (nombre de parts) :**")
parts = CONFIG["impot_revenu"]["parts_fiscales"]
st.dataframe(pd.DataFrame([{"Situation": k.replace("_"," "), "Nb parts": v} for k,v in parts.items()]),
             use_container_width=True, hide_index=True)

# ── 2. Impôt sur les sociétés ────────────────────────────────────────────────
st.header("2. Impôt sur les sociétés (IS) — Taux 2026")
cfg_is = CONFIG["impot_societes"]
col1, col2 = st.columns(2)
with col1:
    st.dataframe(pd.DataFrame([
        {"Tranche de bénéfice": f"≤ {cfg_is['seuil_taux_reduit']:,.0f} €", "Taux IS": f"{cfg_is['taux_reduit']*100:.0f} %", "Condition": "Taux réduit PME"},
        {"Tranche de bénéfice": f"> {cfg_is['seuil_taux_reduit']:,.0f} €", "Taux IS": f"{cfg_is['taux_normal']*100:.0f} %", "Condition": "Taux normal"},
    ]), use_container_width=True, hide_index=True)
with col2:
    cond = cfg_is["conditions_taux_reduit"]
    st.info(f"""**Conditions taux réduit 15% :**
- CA HT ≤ {cond['ca_ht_max']:,.0f} €
- Capital libéré et entièrement versé
- 75% minimum détenu par des personnes physiques""")

# ── 3. Flat tax (PFU) ────────────────────────────────────────────────────────
st.header("3. Flat tax / PFU — Dividendes 2026")
ft = CONFIG["flat_tax"]
detail = ft["detail"]
st.dataframe(pd.DataFrame([
    {"Composante": "IR forfaitaire (PFU)",         "Taux": f"{detail['pfu_ir']*100:.1f} %"},
    {"Composante": "CSG/CRDS",                     "Taux": f"{detail['csg_crds']*100:.1f} %"},
    {"Composante": "Prélèvement social",           "Taux": f"{detail['prelevement_social']*100:.1f} %"},
    {"Composante": "**TOTAL Flat tax**",           "Taux": f"**{ft['taux_global']*100:.1f} %**"},
]), use_container_width=True, hide_index=True)
st.caption("La flat tax s'applique sur les dividendes bruts distribués. Option possible pour le barème progressif de l'IR si plus avantageux.")

# ── 4. Cotisations sociales ───────────────────────────────────────────────────
st.header("4. Cotisations sociales — Régimes 2026")

c1, c2 = st.columns(2)
with c1:
    st.subheader("TNS — SSI (EURL gérant majoritaire)")
    cfg_tns = CONFIG["cotisations_tns"]
    st.dataframe(pd.DataFrame([
        {"Paramètre": "Taux global sur rémunération nette",          "Valeur": f"~{cfg_tns['taux_global_sur_net']*100:.0f} %"},
        {"Paramètre": "Coût pour 1 000 € net versé",                 "Valeur": f"{cfg_tns['cout_total_pour_1000_net']:,.0f} €"},
        {"Paramètre": "Cotisations minimales (sans rémunération)",   "Valeur": f"{cfg_tns['minimum_annuel_sans_remuneration']:,.0f} €/an"},
        {"Paramètre": "Seuil dividendes soumis aux cotisations TNS", "Valeur": f"{cfg_tns['seuil_dividendes_soumis_cotisations_pct']*100:.0f} % du capital social"},
    ]), use_container_width=True, hide_index=True)
    st.caption(cfg_tns["description"])

with c2:
    st.subheader("Assimilé salarié — Régime général (SASU)")
    cfg_sal = CONFIG["cotisations_assimile_salarie"]
    st.dataframe(pd.DataFrame([
        {"Paramètre": "Taux global sur salaire net",     "Valeur": f"~{cfg_sal['taux_global_sur_net']*100:.0f} %"},
        {"Paramètre": "Coût pour 1 000 € net versé",    "Valeur": f"{cfg_sal['cout_total_pour_1000_net']:,.0f} €"},
        {"Paramètre": "Cotisations minimales",           "Valeur": f"{cfg_sal['minimum_annuel']:,.0f} €/an"},
        {"Paramètre": "Dividendes soumis aux cotisations","Valeur": "Non (flat tax uniquement)"},
    ]), use_container_width=True, hide_index=True)
    st.caption(cfg_sal["description"])

# ── 5. Micro-entreprise ───────────────────────────────────────────────────────
st.header("5. Micro-entreprise — Abattements & plafonds 2026")
cfg_me = CONFIG["micro_entreprise"]
st.dataframe(pd.DataFrame([
    {
        "Type d'activité": "Prestations de services (BNC)",
        "Plafond CA": f"{cfg_me['plafond_ca_services_bnc']:,.0f} €",
        "Abattement forfaitaire": f"{cfg_me['abattements']['services_bnc']*100:.0f} %",
        "Taux cotisations sur CA": f"{cfg_me['taux_cotisations_sur_ca']['services_bnc']*100:.1f} %",
    },
    {
        "Type d'activité": "Prestations de services (BIC)",
        "Plafond CA": f"{cfg_me['plafond_ca_services_bic']:,.0f} €",
        "Abattement forfaitaire": f"{cfg_me['abattements']['services_bic']*100:.0f} %",
        "Taux cotisations sur CA": f"{cfg_me['taux_cotisations_sur_ca']['services_bic']*100:.1f} %",
    },
    {
        "Type d'activité": "Commerce / vente de biens",
        "Plafond CA": f"{cfg_me['plafond_ca_commerce']:,.0f} €",
        "Abattement forfaitaire": f"{cfg_me['abattements']['commerce']*100:.0f} %",
        "Taux cotisations sur CA": f"{cfg_me['taux_cotisations_sur_ca']['commerce']*100:.1f} %",
    },
]), use_container_width=True, hide_index=True)
st.caption("L'abattement forfaitaire remplace toutes les charges réelles. Si vos charges réelles sont supérieures à l'abattement, une société sera plus avantageuse.")

# ── 6. Retraite & PASS ────────────────────────────────────────────────────────
st.header("6. Retraite & PASS 2026")
cfg_ret = CONFIG["retraite"]
st.dataframe(pd.DataFrame([
    {"Paramètre": "PASS 2026 (Plafond Annuel Sécurité Sociale)",       "Valeur": f"{cfg_ret['pass_2026']:,.0f} €"},
    {"Paramètre": "Salaire brut minimum pour valider 4 trimestres",    "Valeur": f"{cfg_ret['salaire_brut_min_4_trimestres']:,.0f} €/an"},
    {"Paramètre": "Salaire brut minimum pour valider 1 trimestre",     "Valeur": f"{cfg_ret['salaire_brut_min_1_trimestre']:,.0f} €/an"},
]), use_container_width=True, hide_index=True)
st.info("💡 **Important SASU :** si le salaire brut annuel est inférieur à 7 212 €, vous ne validez pas 4 trimestres de retraite. "
        "Aucune cotisation minimale obligatoire en SASU si salaire = 0 (contrairement à l'EURL).")

# ── 7. PER ────────────────────────────────────────────────────────────────────
st.header("7. Plan d'Épargne Retraite (PER) — Plafonds de déduction TNS 2026")
cfg_per = CONFIG["per"]
st.dataframe(pd.DataFrame([
    {"Paramètre": "Plafond minimum de déduction PER (TNS)",   "Valeur": f"{cfg_per['plafond_deduction_tns_min']:,.0f} €"},
    {"Paramètre": "Plafond maximum de déduction PER (TNS)",   "Valeur": f"{cfg_per['plafond_deduction_tns_max']:,.0f} €"},
]), use_container_width=True, hide_index=True)
st.caption("Les versements sur PER sont déductibles du revenu imposable pour les TNS, dans ces limites.")

# ── 8. Comparatif statuts ─────────────────────────────────────────────────────
st.header("8. Tableau comparatif des statuts juridiques")
statuts = CONFIG["statuts"]
st.dataframe(pd.DataFrame([
    {
        "": "Régime social",
        "Micro": statuts["micro"]["regime_social"],
        "EURL":  statuts["eurl"]["regime_social"],
        "SASU":  statuts["sasu"]["regime_social"],
    },
    {
        "": "Régime fiscal par défaut",
        "Micro": statuts["micro"]["regime_fiscal_defaut"],
        "EURL":  statuts["eurl"]["regime_fiscal_defaut"],
        "SASU":  statuts["sasu"]["regime_fiscal_defaut"],
    },
    {
        "": "Option IS possible",
        "Micro": "❌",
        "EURL":  "✅",
        "SASU":  "✅",
    },
    {
        "": "Dividendes possibles",
        "Micro": "❌",
        "EURL":  "✅ (à l'IS)",
        "SASU":  "✅ (à l'IS)",
    },
    {
        "": "Dividendes soumis cotisations sociales",
        "Micro": "—",
        "EURL":  "✅ si > 10% capital",
        "SASU":  "❌ (flat tax uniquement)",
    },
    {
        "": "Charges réelles déductibles",
        "Micro": "❌ (abattement forfaitaire)",
        "EURL":  "✅",
        "SASU":  "✅",
    },
    {
        "": "Responsabilité",
        "Micro": statuts["micro"]["responsabilite"],
        "EURL":  statuts["eurl"]["responsabilite"],
        "SASU":  statuts["sasu"]["responsabilite"],
    },
    {
        "": "Coût création (estimé)",
        "Micro": f"{statuts['micro']['cout_creation']:,.0f} €",
        "EURL":  f"~{statuts['eurl']['cout_creation']:,.0f} €",
        "SASU":  f"~{statuts['sasu']['cout_creation']:,.0f} €",
    },
    {
        "": "Expert-comptable (estimé/an)",
        "Micro": "Non obligatoire",
        "EURL":  f"{statuts['eurl']['cout_expert_comptable_annuel_min']:,.0f} – {statuts['eurl']['cout_expert_comptable_annuel_max']:,.0f} €",
        "SASU":  f"{statuts['sasu']['cout_expert_comptable_annuel_min']:,.0f} – {statuts['sasu']['cout_expert_comptable_annuel_max']:,.0f} €",
    },
]).set_index(""), use_container_width=True)

st.divider()
st.caption("Source : barèmes 2026 · Fichier de configuration : `data/config.json` · Mis à jour manuellement chaque année")