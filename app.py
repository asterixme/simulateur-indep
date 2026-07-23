"""
app.py — Simulateur de statut juridique 2026
"""
import streamlit as st, sys, pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from core.income import simuler_micro, simuler_eurl, simuler_sasu
from core.tax import _charger_config

CONFIG = _charger_config()

st.set_page_config(page_title="Simulateur Statut Juridique 2026", page_icon="⚖️", layout="wide")

# ─────────────────────────────────────────────────────────────────────────────
# HELPER : affichage d'une ligne de détail
# ─────────────────────────────────────────────────────────────────────────────
def ligne(label: str, valeur, note: str = "", negatif: bool = False, gras: bool = False):
    val_str = f"{valeur:,.0f} €" if isinstance(valeur, (int, float)) else str(valeur)
    if negatif and isinstance(valeur, (int, float)):
        val_str = f"− {valeur:,.0f} €"
    style = "**" if gras else ""
    note_str = f"  \n  <small style='color:grey'>{note}</small>" if note else ""
    st.markdown(f"{style}{label}{style} : {style}{val_str}{style}{note_str}", unsafe_allow_html=True)

def separateur():
    st.markdown("<hr style='margin:6px 0; border-color:#eee'>", unsafe_allow_html=True)

def titre_groupe(emoji: str, label: str):
    st.markdown(f"##### {emoji} {label}")

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS : metriques + detail separes
# -----------------------------------------------------------------------------
def _afficher_metriques(res: dict):
    syn = res['synthese']
    tre = res['tresorerie']
    ent = res['entreprise']
    net_poche    = syn['revenu_net_disponible']
    total_impots = syn['total_impots_et_charges']
    tresorerie   = tre['compte_boite']
    ca_val       = ent['ca']
    st.markdown('---')
    st.metric('💰 En poche / an', f'{net_poche:,.0f} €',
              delta=f'{net_poche/12:,.0f} €/mois', delta_color='normal')
    st.metric('🏛️ Total impôts & charges', f'{total_impots:,.0f} €',
              delta=f'{total_impots/ca_val*100:.0f}% du CA' if ca_val else '—',
              delta_color='inverse')
    if tre['applicable']:
        st.metric('🏦 Trésorerie boîte', f'{tresorerie:,.0f} €',
                  delta='reste en société')
    else:
        st.metric('🏦 Trésorerie boîte', '—', delta='non applicable')
    st.markdown('---')


def _afficher_detail(res: dict):
    rf      = res['regime_fiscal']
    is_mode = (rf == 'IS')
    ent  = res['entreprise']
    sal  = res['salaire']
    div  = res['dividendes']
    tre  = res['tresorerie']
    syn  = res['synthese']

    # ── Revenus entreprise ────────────────────────────────────────────────
    with st.expander("🏢 Revenus entreprise", expanded=True):
        ligne("CA", ent["ca"])
        if ent.get("charges_deductibles", 0):
            ligne("Charges déductibles", ent["charges_deductibles"], negatif=True)
        if ent.get("abattement_forfaitaire", 0):
            ligne("Abattement forfaitaire",
                  ent["abattement_forfaitaire"], negatif=True,
                  note=f"{ent['taux_abattement']*100:.0f}% du CA — remplace les charges réelles")
        ligne("Choix régime", ent["regime_fiscal"])
        separateur()
        if is_mode:
            ligne("Base imposable IS", ent.get("base_imposable_is", 0))
            ligne("Impôt sur les sociétés (IS)",
                  ent["impot_societes"], negatif=True,
                  note=f"Taux effectif {ent['taux_is_effectif']:.1f}% (15% ≤ 42 500€ · 25% au-delà)", gras=True)
            ligne("Reste après IS", ent["reste_apres_impots"], gras=True)
        else:
            ligne("Base imposable IR", ent.get("base_imposable_ir", 0))
            st.caption("En IR, pas d'IS — le bénéfice est imposé directement à l'IR du dirigeant.")

    # ── Salaire / Rémunération ────────────────────────────────────────────
    with st.expander("💼 Salaire / Rémunération", expanded=True):
        if sal.get("mode_ir"):
            # IR : pas de salaire distinct
            ligne("Bénéfice brut (avant cotisations)", sal.get("remuneration_brute", 0))
            ligne("Cotisations sociales",
                  sal["cotisations"], negatif=True,
                  note=sal["detail_cotisations"], gras=True)
            ligne("Bénéfice net (= rémunération disponible)",
                  sal.get("remuneration_nette", 0) or sal.get("remuneration_nette_apres_ir", 0) + sal["ir_personnel"],
                  gras=True)
            separateur()
            ligne("IR personnel (sur ce bénéfice)",
                  sal["ir_personnel"], negatif=True,
                  note=f"TMI {sal['tmi']}% · taux moyen {sal['taux_moyen_ir']}%", gras=True)
            ligne("Rémunération nette après IR", sal.get("remuneration_nette_apres_ir", 0), gras=True)
        else:
            # IS : salaire brut/net clairement séparés
            ligne("Salaire net versé", sal["salaire_net_saisi"])
            ligne("Cotisations sociales",
                  sal["cotisations"], negatif=True,
                  note=sal["detail_cotisations"], gras=True)
            ligne("Salaire brut (coût total pour la boîte)",
                  sal["salaire_brut"],
                  note="= salaire net + cotisations — c'est ce que la boîte paye réellement")
            separateur()
            ligne("IR personnel (sur salaire net)",
                  sal["ir_personnel"], negatif=True,
                  note=f"TMI {sal['tmi']}% · taux moyen {sal['taux_moyen_ir']}%", gras=True)
            ligne("Salaire net après IR personnel", sal["salaire_net_apres_ir"], gras=True)
            separateur()
            ligne("Total charges payées par la boîte pour ce salaire",
                  sal["total_impots_boite_salaire"], negatif=True,
                  note="= cotisations sociales uniquement (l'IR est payé par le dirigeant)")

        if syn.get("trimestres_retraite") is not None:
            t = syn["trimestres_retraite"]
            ic = "🟢" if t == 4 else ("🟡" if t >= 2 else "🔴")
            st.markdown(f"**Trimestres retraite validés** : {ic} {t}/4")

    # ── Dividendes ────────────────────────────────────────────────────────
    if div["applicable"]:
        with st.expander("📈 Dividendes", expanded=False):
            ligne("Dividendes bruts versés", div["dividendes_bruts"])
            seuil = div.get("seuil_tns", 0)
            if seuil and div.get("div_hors_seuil", 0) > 0:
                # EURL : deux tranches avec traitement différent
                st.markdown(f"**Seuil TNS : {seuil:,.0f} € (10% du capital)**")
                separateur()
                st.markdown(f"*Part ≤ seuil : {div['div_sous_seuil']:,.0f} € → Flat tax complète 31,4%*")
                ligne("  IR PFU 12,8%", div["ft_sous_seuil_ir"], negatif=True)
                ligne("  Prél. sociaux 17,2% + PS 1,4%", div["ft_sous_seuil_ps"], negatif=True)
                separateur()
                st.markdown(f"*Part > seuil : {div['div_hors_seuil']:,.0f} € → Cotisations SSI + IR PFU (sans PS)*")
                ligne(f"  Cotisations SSI 45%", div["cotisations_ssi_div"], negatif=True, gras=True)
                ligne("  IR PFU 12,8% (PS remplacés par SSI)", div["ft_hors_seuil_ir"], negatif=True)
                separateur()
            else:
                # SASU ou EURL sous seuil : flat tax simple
                st.caption(div.get("detail_flat_tax", ""))
                ligne("IR PFU 12,8%", div.get("ir_pfu_total", div.get("ft_sous_seuil_ir", 0)), negatif=True)
                ligne("Prél. sociaux 17,2% + PS 1,4%", div.get("ps_total", 0), negatif=True)
            ligne("Dividendes nets reçus", div["dividendes_nets"], gras=True)
            separateur()
            ligne("Total prélèvements sur dividendes", div["total_impots_dividendes"], gras=True,
                  note="Cotisations SSI + flat tax")
    elif not div["applicable"] and is_mode is False:
        with st.expander("📈 Dividendes", expanded=False):
            st.caption(f"⚠️ {div.get('raison', '')}")

    # ── Trésorerie ────────────────────────────────────────────────────────
    with st.expander("🏦 Trésorerie (compte de la boîte)", expanded=True):
        if tre["applicable"]:
            ligne("Solde restant dans la société", tre["compte_boite"], gras=True)
            st.caption(tre.get("detail", ""))
            st.caption("Ce montant est disponible en trésorerie : investissement, épargne entreprise, ou future distribution.")
        else:
            st.caption(f"⚠️ {tre.get('raison', '')}")




# ═════════════════════════════════════════════════════════════════════════════


def afficher_statut(res: dict):
    # Pour la micro (pas de sliders intercales) : metriques + detail d'un coup
    _afficher_metriques(res)
    _afficher_detail(res)


# SECTION 1 — PARAMÈTRES
# ═════════════════════════════════════════════════════════════════════════════
st.title("⚖️ Simulateur de statut juridique 2026")
st.caption("Compare Micro-entreprise, EURL et SASU · Barèmes fiscaux et sociaux 2026")

with st.container(border=True):
    st.subheader("① Paramètres de la simulation")
    c1, c2, c3 = st.columns(3)
    with c1:
        ca = st.number_input("Chiffre d'affaires annuel HT (€)", 0, 2_000_000, 80_000, 1_000)
        type_activite = st.selectbox("Type d'activité",
            ["services_bnc", "services_bic", "commerce"],
            format_func=lambda x: {
                "services_bnc": "Prestations BNC — libéral, consultant…",
                "services_bic": "Prestations BIC — artisan, agence…",
                "commerce"    : "Commerce / vente de biens"}[x])
    with c2:
        charges_reelles = st.number_input("Charges pro réelles (€/an)", 0, 500_000, 5_000, 500,
            help="Loyer, matériel, logiciels, expert-comptable… hors rémunération")
        situation_familiale = st.selectbox("Situation familiale",
            ["celibataire_sans_enfant","celibataire_1_enfant","celibataire_2_enfants","celibataire_3_enfants",
             "marie_sans_enfant","marie_1_enfant","marie_2_enfants","marie_3_enfants"],
            format_func=lambda x: {
                "celibataire_sans_enfant":"Célibataire — sans enfant",
                "celibataire_1_enfant"  :"Célibataire — 1 enfant",
                "celibataire_2_enfants" :"Célibataire — 2 enfants",
                "celibataire_3_enfants" :"Célibataire — 3 enfants",
                "marie_sans_enfant"     :"Marié(e)/Pacsé(e) — sans enfant",
                "marie_1_enfant"        :"Marié(e)/Pacsé(e) — 1 enfant",
                "marie_2_enfants"       :"Marié(e)/Pacsé(e) — 2 enfants",
                "marie_3_enfants"       :"Marié(e)/Pacsé(e) — 3 enfants"}[x])
    with c3:
        capital_social = st.number_input("Capital social EURL/SASU (€)", 1, 100_000, 1_000, 100,
            help="Seuil dividendes EURL soumis aux cotisations TNS = 10% du capital")

nb_parts   = CONFIG["impot_revenu"]["parts_fiscales"][situation_familiale]
benef_brut = max(0, ca - charges_reelles)
cfg_micro  = CONFIG["micro_entreprise"]
plafond    = cfg_micro[f"plafond_ca_{type_activite}"]

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — RÉSULTATS PAR STATUT
# =============================================================================
st.divider()
st.subheader("② Résultats par statut")

cfg_tns        = CONFIG["cotisations_tns"]
taux_cout_tns  = cfg_tns["cout_total_pour_1000_net"] / 1000
seuil_div_eurl = round(capital_social * 0.10)

col_micro, col_eurl, col_sasu = st.columns(3)

# ── MICRO ─────────────────────────────────────────────────────────────────
with col_micro:
    with st.container(border=True):
        st.markdown("### 🟦 Micro-entreprise")
        st.caption("IR · TNS · Pas de dividendes")
        if ca > plafond:
            st.error(f"Non éligible — CA ({ca:,.0f}€) > plafond ({plafond:,.0f}€)")
            res_micro = None
        else:
            res_micro = simuler_micro(ca, type_activite, nb_parts)
            afficher_statut(res_micro)

# ── EURL ──────────────────────────────────────────────────────────────────
with col_eurl:
    with st.container(border=True):
        st.markdown("### 🟨 EURL")
        st.caption("IS ou IR · TNS (SSI) · Dividendes possibles à l'IS")

        # Calcul preview via session_state pour afficher les métriques avant les widgets
        eurl_rf = st.session_state.get("eurl_rf", "IS")
        eurl_is = (eurl_rf == "IS")
        _rem_eurl_cur = st.session_state.get("rem_eurl", min(round(benef_brut * 0.5), int(benef_brut)))
        _div_eurl_cur = st.session_state.get("div_eurl", min(seuil_div_eurl, max(0, int(benef_brut - _rem_eurl_cur * taux_cout_tns))))
        if eurl_is:
            _res_eurl_preview = simuler_eurl(ca, charges_reelles, _rem_eurl_cur, _div_eurl_cur, nb_parts, capital_social, "IS")
        else:
            _res_eurl_preview = simuler_eurl(ca, charges_reelles, 0, 0, nb_parts, capital_social, "IR")

        # Métriques
        _afficher_metriques(_res_eurl_preview)

        # Paramètres
        st.caption("Régime social : **TNS (SSI)** — obligatoire pour le gérant majoritaire")
        eurl_rf = st.radio("Régime fiscal", ["IS", "IR"], key="eurl_rf", horizontal=True)
        eurl_is = (eurl_rf == "IS")

        # 4. Sliders
        if eurl_is:
            rem_eurl = st.slider("Salaire net dirigeant (€/an)",
                0, max(1, int(benef_brut)),
                min(round(benef_brut * 0.5), int(benef_brut)), 500, key="rem_eurl",
                help="NET saisi. Brut = net + cotisations TNS ~45%.")
            cout_sal_eurl = rem_eurl * taux_cout_tns
            div_max_eurl  = max(0, int(benef_brut - cout_sal_eurl))
            div_eurl = st.slider(
                f"Dividendes bruts (€/an) — seuil TNS : {seuil_div_eurl:,} €",
                0, max(1, div_max_eurl), min(seuil_div_eurl, div_max_eurl), 500, key="div_eurl",
                help=f"Au-delà de {seuil_div_eurl:,}€ (10% capital), cotisations TNS supplémentaires")
            res_eurl = simuler_eurl(ca, charges_reelles, rem_eurl, div_eurl, nb_parts, capital_social, "IS")
        else:
            st.caption("En IR, le dirigeant est imposé sur tout le bénéfice — pas de slider.")
            res_eurl = simuler_eurl(ca, charges_reelles, 0, 0, nb_parts, capital_social, "IR")

        # 3. Détail
        _afficher_detail(res_eurl)

# ── SASU ──────────────────────────────────────────────────────────────────
with col_sasu:
    with st.container(border=True):
        st.markdown("### 🟩 SASU")
        st.caption("IS par défaut · Régime social au choix · Dividendes sans cotisations sociales")

        # Calcul preview via session_state pour métriques avant widgets
        cfg_rs_sasu    = CONFIG["cotisations_assimile_salarie"]
        taux_cout_sasu = cfg_rs_sasu["cout_total_pour_1000_net"] / 1000
        _sasu_rf_cur   = st.session_state.get("sasu_rf", "IS")
        _sasu_is_cur   = (_sasu_rf_cur == "IS")
        _sal_sasu_cur  = st.session_state.get("sal_sasu", min(round(CONFIG["retraite"]["salaire_brut_min_4_trimestres"] / 1.82), int(benef_brut)))
        _cout_sal_cur  = _sal_sasu_cur * taux_cout_sasu
        _div_sasu_cur  = st.session_state.get("div_sasu", min(round(max(0, benef_brut - _cout_sal_cur) * 0.7), max(0, int(benef_brut - _cout_sal_cur))))
        if _sasu_is_cur:
            _res_sasu_preview = simuler_sasu(ca, charges_reelles, _sal_sasu_cur, _div_sasu_cur, nb_parts, "IS")
        else:
            _res_sasu_preview = simuler_sasu(ca, charges_reelles, 0, 0, nb_parts, "IR")

        # Métriques en haut
        _afficher_metriques(_res_sasu_preview)

        # Paramètres
        st.caption("👷 Régime social : **Assimilé salarié (Régime général)** — obligatoire pour le président de SASU")
        sasu_rf = st.radio("Régime fiscal", ["IS", "IR"], key="sasu_rf", horizontal=True,
            help="IR sur option, 5 premiers exercices uniquement.")
        sasu_is = (sasu_rf == "IS")

        # Sliders
        if sasu_is:
            sal_sasu = st.slider("Salaire net président (€/an)",
                0, max(1, int(benef_brut)),
                min(round(CONFIG["retraite"]["salaire_brut_min_4_trimestres"] / 1.82), int(benef_brut)),
                500, key="sal_sasu",
                help=f"NET saisi. Coût brut = net × {taux_cout_sasu:.2f} · Min 7 212€ brut = 4 trimestres retraite")
            cout_sal_sasu = sal_sasu * taux_cout_sasu
            div_max_sasu  = max(0, int(benef_brut - cout_sal_sasu))
            div_sasu = st.slider("Dividendes bruts (€/an) — flat tax 31,4%",
                0, max(1, div_max_sasu),
                min(round(div_max_sasu * 0.7), div_max_sasu), 500, key="div_sasu",
                help="Pas de cotisations sociales sur dividendes en SASU — flat tax 31,4% uniquement")
            res_sasu = simuler_sasu(ca, charges_reelles, sal_sasu, div_sasu, nb_parts, "IS")
        else:
            st.caption("En IR, le dirigeant est imposé sur tout le bénéfice — pas de slider.")
            res_sasu = simuler_sasu(ca, charges_reelles, 0, 0, nb_parts, "IR")

        # 3. Détail
        _afficher_detail(res_sasu)

# SECTION 3 — RECOMMANDATION
# ═════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("③ Recommandation & synthèse")

resultats = {}
if res_micro:
    resultats["Micro-entreprise"] = res_micro
resultats[f"EURL ({eurl_rf})"]  = res_eurl
resultats[f"SASU ({sasu_rf}) — Assimilé salarié"] = res_sasu

classement = sorted(resultats.items(),
    key=lambda x: x[1]["synthese"]["revenu_net_disponible"], reverse=True)

medailles = ["🥇", "🥈", "🥉"]
best_nom, best_res = classement[0]
st.success(f"**{medailles[0]} Statut optimal : {best_nom}** — **{best_res['synthese']['revenu_net_disponible']:,.0f} €/an** net en poche")
if best_res["tresorerie"]["applicable"] and best_res["tresorerie"]["compte_boite"] > 0:
    st.info(f"💡 + {best_res['tresorerie']['compte_boite']:,.0f} € en trésorerie dans la société")

# Tableau comparatif
st.markdown("#### Tableau comparatif")
rows = []
for nom, r in classement:
    s   = r["synthese"]
    sal = r["salaire"]
    div = r["dividendes"]
    tre = r["tresorerie"]
    ent = r["entreprise"]
    rows.append({
        "Statut"                          : nom,
        "💰 Net en poche / an"            : f"{s['revenu_net_disponible']:,.0f} €",
        "📅 Net en poche / mois"          : f"{s['revenu_net_disponible']/12:,.0f} €",
        "🏦 Trésorerie boîte"             : f"{tre['compte_boite']:,.0f} €" if tre["applicable"] else "—",
        "🏛️ IS payé"                     : f"{ent['impot_societes']:,.0f} €" if ent.get("impot_societes") else "—",
        "💼 Cotisations sociales"         : f"{sal['cotisations']:,.0f} €  ({sal['taux_cotisations']*100:.0f}%)",
        "📊 IR personnel"                 : f"{sal['ir_personnel']:,.0f} €  (TMI {sal['tmi']}%)",
        "📈 Flat tax dividendes"          : f"{div['montant_flat_tax']:,.0f} €" if div["applicable"] else "—",
        "🔰 Trimestres retraite"          : f"{s['trimestres_retraite']}/4" if s.get("trimestres_retraite") is not None else "N/A",
    })

df = pd.DataFrame(rows).set_index("Statut")
st.dataframe(df, use_container_width=True)

# Points d'attention
st.markdown("#### ⚠️ Points d'attention")
col_a, col_b = st.columns(2)
with col_a:
    if ca > plafond:
        st.error(f"❌ Micro impossible : CA {ca:,.0f}€ > plafond {plafond:,.0f}€")
    abt = cfg_micro["abattements"][type_activite]
    abt_montant = ca * abt
    if charges_reelles > abt_montant:
        st.warning(f"📊 Charges réelles ({charges_reelles:,.0f}€) > abattement micro ({abt_montant:,.0f}€) → société plus avantageuse")
    else:
        st.info(f"📊 Abattement micro ({abt_montant:,.0f}€) ≥ charges réelles ({charges_reelles:,.0f}€) → micro avantageuse sur ce critère")

with col_b:
    seuil_div_eurl = round(capital_social * 0.10)
    if res_eurl["dividendes"]["applicable"] and res_eurl["dividendes"].get("dividendes_bruts", 0) > seuil_div_eurl:
        st.warning(f"⚠️ EURL : dividendes ({res_eurl['dividendes']['dividendes_bruts']:,.0f}€) > seuil TNS ({seuil_div_eurl:,}€) → cotisations TNS supplémentaires")
    if sasu_is:
        trim_sasu = res_sasu["synthese"].get("trimestres_retraite", 0) or 0
        if trim_sasu < 4:
            st.warning(f"⚠️ SASU : {trim_sasu}/4 trimestres retraite validés — augmenter le salaire brut jusqu'à 7 212€/an minimum")

st.divider()
st.caption("⚠️ Simulation indicative — barèmes 2026. Ne constitue pas un conseil fiscal ou juridique. Consultez un expert-comptable.")