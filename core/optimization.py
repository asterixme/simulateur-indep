from core.tax import calculate_net_income

def compare_statuses(revenue):
    results = {}

    for status in ["micro", "sasu", "ei"]:
        results[status] = calculate_net_income(revenue, status)

    best = max(results, key=results.get)

    return best, results

def recommendation(revenue, best_status):
    if best_status == "micro":
        return "Micro-entreprise est la plus adaptée à ton niveau de revenu"

    if best_status == "sasu":
        return "SASU est plus optimisée dans ce scénario"

    return "EI est le meilleur compromis"