"""Stages 6 and 7: Human review and the learning loop.

Approve or adjust: the decision's actions are written back to the CRM and Slack
(queued in the outbox for the connectors to deliver).
Reject: nothing is written, and the reason is kept.
Every outcome updates the owning agent's weight, so its future recommendations
rank higher or lower.
"""
from .db import audit, get_setting, j, now_iso, one, rows

WEIGHT_STEP = {"approve": 0.05, "adjust": 0.02, "reject": -0.08}
WEIGHT_MIN, WEIGHT_MAX = 0.5, 1.5
STATUS = {"approve": "approved", "adjust": "adjusted", "reject": "rejected"}
WRITABLE_FIELDS = {"forecast_category", "close_date", "stage", "amount"}


def _write_back(conn, decision, value_override=None, note=""):
    action = decision["action"] or {}
    crm = get_setting(conn, "crm_system", "hubspot")
    written = []
    for op in action.get("crm", []):
        op = dict(op)
        if value_override is not None and op["op"] == "update":
            op["value"] = value_override
        if note:
            op["reviewer_note"] = note
        target = f"{crm}:{op['object']}/{op.get('id') or op.get('account_id') or 'new'}"
        conn.execute("INSERT INTO outbox (ts, channel, target, payload, decision_id) VALUES (?,?,?,?,?)",
                     (now_iso(), "crm", target, j(op), decision["id"]))
        # Mirror the change locally so the app shows the CRM state after write-back.
        if op["op"] == "update" and op["field"] in WRITABLE_FIELDS:
            conn.execute(f"UPDATE opportunities SET {op['field']} = ? WHERE id = ?", (op["value"], op["id"]))
        elif op["op"] == "create" and op["object"] == "Opportunity":
            new_id = f"opp-{op['account_id']}-x{decision['id']}"
            conn.execute(
                "INSERT OR IGNORE INTO opportunities (id, account_id, name, amount, currency, stage, close_date, "
                "original_close_date, forecast_category, owner, meddpicc, last_activity) "
                "VALUES (?,?,?,?,?,'Discovery',date('now','+90 day'),date('now','+90 day'),'pipeline',"
                "'Account owner','{}',date('now'))",
                (new_id, op["account_id"], op["name"], op["amount"], op["currency"]))
        written.append(target)
    for msg in action.get("slack", []):
        conn.execute("INSERT INTO outbox (ts, channel, target, payload, decision_id) VALUES (?,?,?,?,?)",
                     (now_iso(), "slack", msg["channel"], j({**msg, "reviewer_note": note}), decision["id"]))
        written.append(f"slack:{msg['channel']}")
    return written


def review(conn, decision_id, verdict, reviewer="leader", note="", value=None):
    if verdict not in STATUS:
        raise ValueError("verdict must be approve, adjust or reject")
    d = one(conn, "SELECT * FROM decisions WHERE id = ?", (decision_id,))
    if not d:
        raise LookupError(f"Decision {decision_id} not found")
    if d["status"] != "pending":
        raise ValueError(f"Decision {decision_id} is already {d['status']}")
    if verdict in ("adjust", "reject") and not note.strip():
        raise ValueError("Please give a reason. The engine learns from it.")

    written = _write_back(conn, d, value, note) if verdict != "reject" else []
    conn.execute("UPDATE decisions SET status = ?, reviewed_by = ?, review_note = ?, adjustment = ?, "
                 "updated_at = ? WHERE id = ?",
                 (STATUS[verdict], reviewer, note, j({"value": value}) if value is not None else None,
                  now_iso(), decision_id))

    w = one(conn, "SELECT weight FROM agent_weights WHERE agent = ?", (d["agent"],))
    new_weight = round(min(WEIGHT_MAX, max(WEIGHT_MIN, (w["weight"] if w else 1.0) + WEIGHT_STEP[verdict])), 3)
    conn.execute(f"INSERT INTO agent_weights (agent, weight, {STATUS[verdict]}) VALUES (?, ?, 1) "
                 f"ON CONFLICT(agent) DO UPDATE SET weight = excluded.weight, "
                 f"{STATUS[verdict]} = {STATUS[verdict]} + 1", (d["agent"], new_weight))

    audit(conn, reviewer, f"decision_{STATUS[verdict]}", decision_id,
          {"note": note, "value": value, "written_to": written,
           "agent": d["agent"], "agent_weight": new_weight})
    conn.commit()
    return {"id": decision_id, "status": STATUS[verdict], "written_to": written,
            "agent": d["agent"], "agent_weight": new_weight}


def learning_summary(conn):
    return rows(conn, "SELECT * FROM agent_weights ORDER BY weight DESC")
