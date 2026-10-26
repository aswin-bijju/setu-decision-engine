"""Stage 4: Prioritise. Score every candidate and keep only the few that deserve a leader's time."""
from .db import get_setting, rows

IMPACT_CAP_EUR = 400000  # impact at or above this scores 1.0
W_IMPACT, W_URGENCY, W_FIT = 0.45, 0.35, 0.20
MAX_PER_ACCOUNT = 2  # extra flags on the same account are folded into its top decision


def agent_weights(conn):
    return {r["agent"]: r["weight"] for r in rows(conn, "SELECT agent, weight FROM agent_weights")}


def score(c, weights):
    impact = min(1.0, c["impact_eur"] / IMPACT_CAP_EUR)
    base = W_IMPACT * impact + W_URGENCY * c["urgency"] + W_FIT * c["strategic_fit"]
    return round(base * c["confidence"] * weights.get(c["agent"], 1.0), 4)


def prioritise(conn, candidates):
    """Return (kept, discarded). Learned agent weights scale each score."""
    weights = agent_weights(conn)
    for c in candidates:
        c["priority"] = score(c, weights)
    ranked = sorted(candidates, key=lambda c: c["priority"], reverse=True)
    size = int(get_setting(conn, "queue_size", 10))
    kept, discarded, per_account = [], [], {}
    for c in ranked:
        acc = c["account_id"]
        if acc and len(per_account.get(acc, [])) >= MAX_PER_ACCOUNT:
            lead = per_account[acc][0]
            lead["reasoning"].append(f"Also flagged by the {c['agent']} agent: {c['title']}.")
            lead["evidence"] = list(dict.fromkeys(lead["evidence"] + c["evidence"]))
            discarded.append(c)
        elif len(kept) >= size:
            discarded.append(c)
        else:
            kept.append(c)
            per_account.setdefault(acc, []).append(c)
    return kept, discarded
