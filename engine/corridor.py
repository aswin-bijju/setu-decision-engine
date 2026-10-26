"""EU-India corridor knowledge: FX, slowdown calendars, fiscal years, regulation, buyer norms.

This is the layer that makes the engine specific to EU-India business relations.
Values marked illustrative should be replaced with live feeds in production.
"""
import os
from datetime import date, timedelta

# Illustrative EUR/INR rate. Set SETU_EUR_INR or wire a live FX feed.
EUR_INR = float(os.environ.get("SETU_EUR_INR", "98.0"))
FX_ALERT_THRESHOLD = 0.03  # alert when INR deal value moves 3% or more in EUR terms

# Approximate Diwali dates; the slowdown window is the date plus or minus 4 days.
DIWALI = {2025: date(2025, 10, 20), 2026: date(2026, 11, 8),
          2027: date(2027, 10, 29), 2028: date(2028, 10, 17)}


def to_eur(amount, currency, rate=None):
    if currency == "INR":
        return amount / (rate or EUR_INR)
    return amount


def slowdown_windows(year):
    windows = [
        ("EU", "Christmas and New Year", date(year, 12, 20), date(year + 1, 1, 6)),
        ("EU", "August summer holidays", date(year, 8, 1), date(year, 8, 31)),
    ]
    if year in DIWALI:
        d = DIWALI[year]
        windows.append(("IN", "Diwali", d - timedelta(days=4), d + timedelta(days=4)))
    return windows


def slowdown_for(close, region):
    """Return the holiday window a close date falls into for the buyer's region, if any."""
    for year in (close.year - 1, close.year):
        for reg, name, start, end in slowdown_windows(year):
            if reg == region and start <= close <= end:
                return name, start, end
    return None


def india_fiscal_note(close):
    if close.month in (2, 3):
        return ("Indian fiscal year ends 31 March. Unspent budget is often released in Q4, "
                "so aim for signature before year end.")
    if close.month in (4, 5):
        return ("New Indian fiscal year budgets open in April. Re-confirm that the deal is "
                "in the FY plan before forecasting it.")
    return None


REGULATIONS = {
    "data_transfer": {
        "title": "GDPR and India DPDP Act 2023",
        "keywords": ["scc", "standard contractual", "dpdp", "gdpr", "data transfer", "dpa"],
        "play": ("Send a cross-border data pack: GDPR Standard Contractual Clauses, a transfer "
                 "impact assessment, and your position under India's DPDP Act 2023."),
    },
    "cbam": {
        "title": "EU Carbon Border Adjustment Mechanism",
        "industries": ["EV components", "Steel", "Aluminium", "Automotive", "Fertiliser", "Cement"],
        "keywords": ["cbam", "embedded emissions"],
        "play": ("Lead with CBAM readiness: EU importers need verified embedded-emissions data "
                 "from Indian suppliers, so frame the product as protecting EU revenue."),
    },
    "dora": {
        "title": "EU Digital Operational Resilience Act",
        "industries": ["Banking", "Insurance"],
        "keywords": ["dora", "ict risk", "register of information"],
        "play": ("Map the offer to DORA third-party ICT risk duties, including the register of "
                 "information and exit plans for providers based in India."),
    },
    "works_council": {
        "title": "Works council co-determination",
        "countries": ["DE", "AT", "NL"],
        "keywords": ["betriebsrat", "works council", "ondernemingsraad"],
        "play": ("Add the works council to the mutual action plan now. Tools that process "
                 "employee data usually need their review before signature."),
    },
}

BUYER_NORMS = {
    "DE": ("Expect detailed documentation, references from comparable German firms and a "
           "formal, staged decision process. The works council may review tools that touch "
           "employee data."),
    "NL": ("Direct and consensus-driven. Procurement and legal join early, so be explicit "
           "about data handling and contract terms from the first proposal."),
    "FR": ("Senior sponsorship carries weight. French-language material helps when the "
           "rollout reaches teams beyond headquarters."),
    "PL": ("Price-performance and implementation speed weigh heavily. References from CEE "
           "peers in the same sector help."),
    "IN": ("In mid-size firms the MD or promoter family often makes the final call. Budgets "
           "follow the April to March fiscal year, and a clear ROI case plus a senior "
           "relationship matter more than feature depth."),
}


def norms_for(country):
    return BUYER_NORMS.get(country, "No country-specific notes yet. Add them in corridor.py.")
