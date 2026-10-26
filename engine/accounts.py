"""Account intelligence: ICP discovery, living account plans, buying committees, seller plays."""
from datetime import date, timedelta

from . import corridor, meddpicc
from .db import get_setting, one, rows

COMMITTEE_ROLES = {
    "champion": "Champion",
    "economic_buyer": "Economic buyer",
    "technical": "Technical evaluator",
    "procurement": "Procurement",
    "legal": "Legal / data protection",
}
ENGAGED_WITHIN_DAYS = 21  # matches the Champion agent's quiet threshold
SIGNAL_POINTS = {"expansion_news": 0.15, "funding": 0.15, "hiring": 0.1, "intent": 0.15,
                 "trade_news": 0.1, "regulatory_news": 0.05}


def _recent_events(conn, account_id, days=45):
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return rows(conn, "SELECT * FROM events WHERE account_id = ? AND occurred_at >= ? "
                      "ORDER BY occurred_at DESC", (account_id, cutoff))


def icp_rank(conn):
    """Score accounts without an open deal against the ideal customer profile."""
    industries = set(get_setting(conn, "icp_industries", []))
    strategy = get_setting(conn, "strategy", {})
    customer_industries = {r["industry"] for r in rows(conn, "SELECT industry FROM accounts WHERE is_customer = 1")}
    out = []
    for acc in rows(conn, "SELECT * FROM accounts WHERE is_customer = 0 AND id NOT IN "
                          "(SELECT account_id FROM opportunities WHERE status = 'open')"):
        score, reasons = 0.0, []
        if acc["industry"] in industries:
            score += 0.2
            reasons.append(f"Target industry: {acc['industry']}")
        if acc["industry"] in customer_industries:
            score += 0.1
            reasons.append("Similar to existing customers")
        if 500 <= (acc["employees"] or 0) <= 10000:
            score += 0.15
            reasons.append(f"Size fit: {acc['employees']:,} employees")
        if acc["territory"] in strategy.get("focus_territories", []):
            score += 0.1
            reasons.append(f"Focus territory: {acc['territory']}")
        signal_score = 0.0
        evidence = []
        for e in _recent_events(conn, acc["id"]):
            pts = SIGNAL_POINTS.get(e["kind"], 0)
            if pts:
                signal_score += pts
                evidence.append(e["text"])
        score += min(0.45, signal_score)
        reasons += evidence
        out.append({"account": acc, "score": round(min(1.0, score), 2), "reasons": reasons,
                    "plays": outreach_plays(conn, acc)[:2]})
    return sorted(out, key=lambda r: r["score"], reverse=True)


def buying_committee(conn, acc):
    people = rows(conn, "SELECT * FROM stakeholders WHERE account_id = ?", (acc["id"],))
    roles = dict(COMMITTEE_ROLES)
    if acc["country"] in corridor.REGULATIONS["works_council"]["countries"]:
        roles["works_council"] = "Works council"
    cutoff = (date.today() - timedelta(days=ENGAGED_WITHIN_DAYS)).isoformat()
    coverage = []
    for role, label in roles.items():
        holders = [p for p in people if p["role"] == role]
        if not holders:
            coverage.append({"role": role, "label": label, "status": "missing", "people": []})
            continue
        active = [p for p in holders if p["status"] == "active"]
        engaged = [p for p in active if (p["last_engaged"] or "") >= cutoff]
        status = "engaged" if engaged else ("departed" if not active else "stale")
        coverage.append({"role": role, "label": label, "status": status, "people": holders})
    gaps = [c["label"] for c in coverage if c["status"] != "engaged"]
    engaged_count = sum(1 for c in coverage if c["status"] == "engaged")
    return {"coverage": coverage, "gaps": gaps, "single_threaded": engaged_count <= 1,
            "others": [p for p in people if p["role"] not in roles]}


def outreach_plays(conn, acc):
    """Openers and next-best actions built from live signals plus corridor norms."""
    plays = []
    for e in _recent_events(conn, acc["id"], days=60):
        k, t = e["kind"], e["text"]
        if k == "expansion_news":
            plays.append({"angle": "New India or EU footprint",
                          "opener": f"Saw the news: \"{t}\". Teams setting up across the corridor usually hit "
                                    "the same three issues in the first six months. Worth 20 minutes to compare notes?"})
        elif k == "funding":
            plays.append({"angle": "Funded expansion",
                          "opener": "Congratulations on the round. If Europe is part of the plan, we can share "
                                    "what worked for other Indian firms entering DACH and Benelux."})
        elif k == "hiring":
            plays.append({"angle": "Hiring signal",
                          "opener": f"Noticed you are hiring ({t}). New teams ramp faster when commercial "
                                    "context is already in one place."})
        elif k == "trade_news":
            plays.append({"angle": "EU-India trade developments",
                          "opener": "Tariff and market-access changes under discussion could shift EU demand. "
                                    "We help exporters see which accounts move first."})
        elif k == "intent":
            plays.append({"angle": "Active research",
                          "opener": "You have been looking at how others handle this. Happy to send a "
                                    "two-page summary from a similar company, no call needed."})
        elif k == "regulatory_news" or "cbam" in t.lower():
            plays.append({"angle": "Regulation as a deadline",
                          "opener": "EU importers are asking suppliers for CBAM emissions data. Being ready "
                                    "first protects your EU orders."})
    plays.append({"angle": "Buyer norms", "opener": corridor.norms_for(acc["country"])})
    seen, unique = set(), []
    for p in plays:
        if p["angle"] not in seen:
            seen.add(p["angle"])
            unique.append(p)
    return unique


def account_plan(conn, account_id):
    acc = one(conn, "SELECT * FROM accounts WHERE id = ?", (account_id,))
    if not acc:
        return None
    opps = rows(conn, "SELECT * FROM opportunities WHERE account_id = ? ORDER BY close_date", (account_id,))
    for o in opps:
        o["amount_eur"] = round(corridor.to_eur(o["amount"], o["currency"]))
        o["inspection"] = meddpicc.inspect(o)
    decisions = rows(conn, "SELECT id, title, agent, status, priority FROM decisions WHERE account_id = ? "
                           "ORDER BY id DESC LIMIT 10", (account_id,))
    regs = []
    text = " ".join(e["text"].lower() for e in _recent_events(conn, account_id, 90))
    for reg in corridor.REGULATIONS.values():
        if (acc["industry"] in reg.get("industries", []) or any(k in text for k in reg["keywords"])) \
                and acc["country"] in reg.get("countries", [acc["country"]]):
            regs.append({"title": reg["title"], "play": reg["play"]})
    return {"account": acc, "opportunities": opps, "committee": buying_committee(conn, acc),
            "signals": _recent_events(conn, account_id, 90), "plays": outreach_plays(conn, acc),
            "corridor": {"direction": acc["corridor"], "buyer_norms": corridor.norms_for(acc["country"]),
                         "regulations": regs},
            "decisions": decisions}
