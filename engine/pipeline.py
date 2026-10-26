"""The engine run: Observe, Understand, Reason, Prioritise, Recommend.

Review and Learn happen afterwards, when a human acts on the queue (see review.py).
"""
from datetime import date, timedelta

from . import agents, llm
from .agents import build_context, manager_agent
from .db import audit, j, now_iso, one, rows
from .ingest import resolve_pending
from .prioritise import prioritise

REJECTION_COOLDOWN_DAYS = 14


def _store(conn, run_id, c, today):
    """Insert or refresh a decision. Respects recent rejections unless new evidence arrived."""
    existing = one(conn, "SELECT * FROM decisions WHERE key = ? ORDER BY id DESC LIMIT 1", (c["key"],))
    if existing and existing["status"] == "rejected":
        recent = (existing["updated_at"] or "")[:10] >= (today - timedelta(days=REJECTION_COOLDOWN_DAYS)).isoformat()
        if recent and set(c["evidence"]) <= set(existing["evidence"] or []):
            return None
    fields = ("agent", "type", "title", "account_id", "opportunity_id", "owner", "recommendation",
              "confidence", "impact_eur", "urgency", "strategic_fit", "priority")
    json_fields = ("reasoning", "evidence", "counter_signals", "action")
    values = [c[f] for f in fields] + [j(c[f]) for f in json_fields]
    if existing and existing["status"] == "pending":
        sets = ", ".join(f"{f} = ?" for f in fields + json_fields)
        conn.execute(f"UPDATE decisions SET {sets}, run_id = ?, updated_at = ? WHERE id = ?",
                     values + [run_id, now_iso(), existing["id"]])
        return existing["id"]
    if existing and existing["status"] in ("approved", "adjusted"):
        return None  # already acted on
    cols = ", ".join(fields + json_fields)
    cur = conn.execute(
        f"INSERT INTO decisions ({cols}, key, run_id, status, created_at, updated_at) "
        f"VALUES ({', '.join('?' * len(values))}, ?, ?, 'pending', ?, ?)",
        values + [c["key"], run_id, now_iso(), now_iso()])
    audit(conn, "engine", "decision_created", cur.lastrowid, {"agent": c["agent"], "title": c["title"]})
    return cur.lastrowid


def executive_briefing(ctx, kept, use_llm=True):
    """The Executive agent: owns the commercial narrative for leadership."""
    at_risk = sum(c["impact_eur"] for c in kept if c["type"] == "forecast_downgrade")
    upside = sum(c["impact_eur"] for c in kept if c["type"] == "expansion_open")
    corridor_items = [c for c in kept if c["type"] == "corridor_risk"]
    lines = [f"{i}. {c['title']} ({c['agent']} agent, {c['confidence']:.0%} confidence)"
             for i, c in enumerate(kept[:3], 1)]
    if use_llm:
        prompt = ("Write a leadership briefing of at most 120 words for a B2B sales team selling across the "
                  "EU-India corridor. Plain, direct sentences. No em dashes, no buzzwords. Start with the "
                  "single most important call. Decisions, highest priority first:\n" +
                  "\n".join(f"- {c['title']}: {c['recommendation']} Reasoning: {' '.join(c['reasoning'])}"
                            for c in kept))
        text = llm.complete("You are the Executive agent of a commercial decision engine.", prompt)
        if text:
            return text
    parts = [f"{len(kept)} decisions need a call this week."]
    if at_risk:
        parts.append(f"€{at_risk:,.0f} of Commit forecast is not supported by current evidence.")
    if upside:
        parts.append(f"€{upside:,.0f} of expansion upside is waiting at existing customers.")
    if corridor_items:
        n = len(corridor_items)
        parts.append(f"{n} {'deal carries' if n == 1 else 'deals carry'} EU-India timing, FX or regulatory risk.")
    parts.append("Top calls: " + " ".join(lines))
    return " ".join(parts)


def run_engine(conn, today=None, use_llm=True):
    today = today or date.today()
    started = now_iso()
    run_id = conn.execute("INSERT INTO runs (started_at) VALUES (?)", (started,)).lastrowid

    resolved = resolve_pending(conn)                      # Observe + Understand
    ctx = build_context(conn, today)
    candidates = [c for agent in agents.SPECIALISTS for c in agent(ctx)]   # Reason
    candidates += manager_agent(ctx, candidates)
    kept, discarded = prioritise(conn, candidates)        # Prioritise
    stored = [i for i in (_store(conn, run_id, c, today) for c in kept) if i]  # Recommend

    # Pending decisions that this run no longer supports are superseded, not left to rot.
    keys = [c["key"] for c in kept]
    marks = ",".join("?" * len(keys)) or "''"
    for d in rows(conn, f"SELECT id FROM decisions WHERE status = 'pending' AND key NOT IN ({marks})", keys):
        conn.execute("UPDATE decisions SET status = 'superseded', updated_at = ? WHERE id = ?", (now_iso(), d["id"]))
        audit(conn, "engine", "decision_superseded", d["id"])

    briefing = executive_briefing(ctx, kept, use_llm)
    stats = {"events_resolved": resolved, "events_total": len(ctx.events),
             "candidates": len(candidates), "surfaced": len(kept), "discarded": len(discarded),
             "discarded_titles": [c["title"] for c in discarded],
             "by_agent": {a: sum(1 for c in candidates if c["agent"] == a)
                          for a in dict.fromkeys(c["agent"] for c in candidates)}}
    conn.execute("UPDATE runs SET finished_at = ?, stats = ?, briefing = ? WHERE id = ?",
                 (now_iso(), j(stats), briefing, run_id))
    audit(conn, "engine", "run_completed", None, {"run_id": run_id, **{k: v for k, v in stats.items()
                                                                      if k != "discarded_titles"}})
    conn.commit()
    return {"run_id": run_id, "briefing": briefing, "stats": stats, "decision_ids": stored}
