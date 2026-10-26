"""Stages 1 and 2: Observe and Understand.

Observe: connectors push raw signals into the events table.
Understand: each event is resolved to an account, opportunity, stakeholder and
competitor, then classified and scored for sentiment.
"""
import random
import re
from datetime import date

from .db import j, now_iso, one, rows

SOURCES = ["crm", "calendar", "calls", "slack", "email", "buying_signals",
           "financial_reports", "product_usage", "hiring", "news"]

LEGAL_SUFFIX = re.compile(r"\b(gmbh|ag|n\.v\.|nv|s\.a\.|sa|pvt|ltd|plc|se|inc)(?=\W|$)", re.I)

# Buyer-side engagement refreshes stakeholder recency; deal activity refreshes the opportunity.
ENGAGEMENT_KINDS = {"meeting", "identify_pain", "pricing", "decision_process", "paper_process",
                    "competitor_mention"}
ACTIVITY_KINDS = ENGAGEMENT_KINDS | {"close_date_pushed", "no_reply"}

# Ordered rules: the first matching kind wins.
KIND_RULES = [
    ("champion_departed", ["left the company", "new role at", "moving on", "departure"]),
    ("close_date_pushed", ["close date", "moved from", "pushed to"]),
    ("paper_process", ["contractual clauses", "contract", "msa", "dpa", "scc", "dpdp", "redline"]),
    ("decision_process", ["sign-off", "betriebsrat", "works council", "steering committee", "approval"]),
    ("usage_down", ["usage down", "users down", "unused"]),
    ("usage_up", ["usage up", "users up", "against 100 licensed", "over licence"]),
    ("intent", ["visited", "downloaded", "webinar", "pricing page"]),
    ("funding", ["raises", "series a", "series b", "funding round"]),
    ("regulatory_news", ["cbam", "dora", "nis2", "regulation"]),
    ("trade_news", ["fta", "trade agreement"]),
    ("expansion_news", ["capability centre", "shared-services", "opens", "new office", "expands", "expand into"]),
    ("hiring", ["hiring", "job posting", "posts", "roles"]),
    ("pricing", ["pricing", "quote", "discount"]),
    ("no_reply", ["unanswered", "no reply"]),
    ("meeting", ["meeting", "workshop", "qbr", "call with"]),
]

POSITIVE = ["going well", "confirms", "progress", "up ", "raises", "expand", "keen", "approved"]
NEGATIVE = ["unanswered", "moved from", "left", "down", "unused", "also looking", "not looped",
            "delay", "concern", "competitor", "requires"]


def short_name(name):
    return LEGAL_SUFFIX.sub("", name).replace(",", "").strip().lower()


def classify(text, competitor=None):
    t = text.lower()
    if competitor:
        hiring = any(w in t for w in ("hiring", "posts", "roles"))
        return "competitor_hiring" if hiring else "competitor_mention"
    for kind, words in KIND_RULES:
        if any(w in t for w in words):
            return kind
    return "note"


def sentiment(text):
    t = text.lower()
    score = sum(0.25 for w in POSITIVE if w in t) - sum(0.25 for w in NEGATIVE if w in t)
    return max(-1.0, min(1.0, score))


def ingest(conn, source, text, occurred_at=None, payload=None, kind=None):
    if source not in SOURCES:
        raise ValueError(f"Unknown source '{source}'. Use one of: {', '.join(SOURCES)}")
    if not text or not text.strip():
        raise ValueError("Signal text is required")
    cur = conn.execute(
        "INSERT INTO events (source, occurred_at, text, payload, kind, ingested_at) VALUES (?,?,?,?,?,?)",
        (source, occurred_at or date.today().isoformat(), text.strip(), j(payload or {}), kind, now_iso()))
    conn.commit()
    return cur.lastrowid


def resolve_pending(conn):
    """Entity resolution for every unresolved event. Returns the number resolved."""
    accounts = rows(conn, "SELECT id, name, domain FROM accounts")
    stakeholders = rows(conn, "SELECT id, account_id, name, email FROM stakeholders")
    competitors = rows(conn, "SELECT id, name, aliases FROM competitors")
    pending = rows(conn, "SELECT * FROM events WHERE resolved = 0 ORDER BY occurred_at")

    for ev in pending:
        text, payload = ev["text"], ev["payload"] or {}
        lower = text.lower()
        email = (payload.get("email") or "").lower()

        stakeholder = next((s for s in stakeholders if email and s["email"].lower() == email), None)
        if not stakeholder:
            stakeholder = next((s for s in stakeholders if s["name"].lower().replace("dr. ", "") in lower), None)

        account = None
        hint = (payload.get("account") or "").lower()
        if hint:
            account = next((a for a in accounts if hint in (a["id"], a["name"].lower())), None)
        if not account and email and "@" in email:
            account = next((a for a in accounts if email.split("@")[1] == a["domain"]), None)
        if not account and stakeholder:
            account = next(a for a in accounts if a["id"] == stakeholder["account_id"])
        if not account:
            # Match on the distinctive first word of the name, e.g. "rheinwerk", "kaveri".
            account = next((a for a in accounts if short_name(a["name"]) in lower
                            or short_name(a["name"]).split()[0] in lower.split()), None)

        competitor = next((c for c in competitors
                           if any(alias in lower for alias in c["aliases"])), None)

        opp = None
        if account:
            opp = one(conn, "SELECT id FROM opportunities WHERE account_id = ? AND status = 'open' "
                            "ORDER BY close_date LIMIT 1", (account["id"],))

        kind = ev["kind"] or classify(text, competitor)
        conn.execute(
            "UPDATE events SET account_id = ?, opportunity_id = ?, stakeholder_id = ?, competitor_id = ?, "
            "kind = ?, sentiment = ?, resolved = 1 WHERE id = ?",
            (account and account["id"], opp and opp["id"], stakeholder and stakeholder["id"],
             competitor and competitor["id"], kind, sentiment(text), ev["id"]))

        # Engagement from the buyer side refreshes CRM recency fields.
        if stakeholder and kind in ENGAGEMENT_KINDS:
            conn.execute("UPDATE stakeholders SET last_engaged = MAX(COALESCE(last_engaged, ''), ?) "
                         "WHERE id = ?", (ev["occurred_at"], stakeholder["id"]))
        if opp and kind in ACTIVITY_KINDS:
            conn.execute("UPDATE opportunities SET last_activity = MAX(COALESCE(last_activity, ''), ?) "
                         "WHERE id = ?", (ev["occurred_at"], opp["id"]))
        if kind == "champion_departed" and stakeholder:
            conn.execute("UPDATE stakeholders SET status = 'departed' WHERE id = ?", (stakeholder["id"],))
    conn.commit()
    return len(pending)


SIMULATED = [
    ("email", "Sabine Krüger (CFO) asked for a payback calculation before the steering committee",
     {"email": "sabine.krueger@rheinwerk-automation.de"}),
    ("product_usage", "Lumière Retail: Hyderabad hub requested 30 more seats", {"account": "lumiere"}),
    ("hiring", "Vistula Logistics is hiring 20 finance roles for its Pune shared-services centre", {}),
    ("calls", "Call with Eva de Vries: Meridian Consulting quoted a 9-month implementation",
     {"email": "eva.devries@noordbank.nl"}),
    ("news", "Malabar Foods Export wins listing with a German supermarket chain", {}),
    ("buying_signals", "Saffron Analytics visited the pricing page 4 times this week", {}),
    ("email", "Vikram Desai: we are reviewing whether to renew the EU dossier module",
     {"email": "vikram.desai@induspharma.in"}),
    ("slack", "#deal-rheinwerk: Dr. Weber is on leave until next month, per his assistant",
     {"account": "rheinwerk"}),
]


def simulate(conn):
    source, text, payload = random.choice(SIMULATED)
    return ingest(conn, source, text, payload=payload)
