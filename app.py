import streamlit as st

from core.income import calculate_revenue
from core.tax import calculate_net_income
from core.optimization import compare_statuses, recommendation

st.title("Simulateur indépendant")

with st.expander("Informations personnelles"):
    # Inputs utilisateur
    tjm = st.number_input("TJM", value=0)
    days = st.number_input("Jours travaillés", value=0)


with st.expander("Informations professionnelles"):
    # Sélection du statut utilisateur (scénario courant)
    current_status = st.selectbox("Statut actuel", ["micro", "sasu", "ei"])

with st.expander("Résulats simulation"):
    # Calcul revenu brut
    revenue = calculate_revenue(tjm, days)


    # Calcul net du scénario actuel
    net_current = calculate_net_income(revenue, current_status)

    # Optimisation globale
    best_status, comparison = compare_statuses(revenue)
    rec = recommendation(revenue, best_status)

    # Affichage
    st.subheader("Résultats")

    st.write("Revenu brut :", revenue)
    st.write("Revenu net (scénario actuel) :", net_current)

    st.subheader("Comparaison des statuts")
    st.write(comparison)

    st.subheader("Optimisation")
    st.write("Meilleur statut :", best_status)
    st.write(rec)