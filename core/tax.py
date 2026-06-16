def micro_social_charges(revenue):
    """
    Approximation micro-entreprise :
    - ~22% de charges sociales (service)
    """
    return revenue * 0.22


def micro_income_tax(revenue_after_charges):
    """
    Approximation très simplifiée :
    abattement + impôt moyen simulé
    (volontairement simplifié pour MVP)
    """
    taxable = revenue_after_charges * 0.66
    return taxable * 0.11


def sasu_charges(revenue):
    """
    Très simplifié :
    - charges sociales + gestion entreprise
    """
    return revenue * 0.45


def ei_charges(revenue):
    """
    Approximation EI classique
    """
    return revenue * 0.35


def calculate_net_income(revenue, status):
    """
    Retourne revenu net estimé selon statut
    """
    if status == "micro":
        charges = micro_social_charges(revenue)
        net_after_charges = revenue - charges
        tax = micro_income_tax(net_after_charges)
        return net_after_charges - tax

    elif status == "sasu":
        charges = sasu_charges(revenue)
        return revenue - charges

    elif status == "ei":
        charges = ei_charges(revenue)
        return revenue - charges

    else:
        return revenue