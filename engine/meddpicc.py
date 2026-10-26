"""MEDDPICC deal inspection."""

ELEMENTS = [
    ("metrics", "Metrics", "What measurable outcome does the buyer expect, in EUR or INR?"),
    ("economic_buyer", "Economic buyer", "Who signs, and have we met them directly?"),
    ("decision_criteria", "Decision criteria", "What will they judge vendors on, in their words?"),
    ("decision_process", "Decision process", "Which steps and committees remain before signature?"),
    ("paper_process", "Paper process", "What do procurement, legal and data protection need from us?"),
    ("identify_pain", "Identified pain", "What happens if they do nothing this year?"),
    ("champion", "Champion", "Who sells for us internally when we are not in the room?"),
    ("competition", "Competition", "Who else is in the evaluation, including doing it in-house?"),
]
LABELS = {k: label for k, label, _ in ELEMENTS}
SCORES = {"confirmed": 1.0, "weak": 0.5, "missing": 0.0}


def inspect(opp):
    data = opp.get("meddpicc") or {}
    elements, total = [], 0.0
    for key, label, question in ELEMENTS:
        item = data.get(key, {"status": "missing", "note": ""})
        status = item.get("status", "missing")
        total += SCORES.get(status, 0)
        elements.append({"key": key, "label": label, "status": status,
                         "note": item.get("note", ""),
                         "next_question": question if status != "confirmed" else ""})
    return {"score": round(100 * total / len(ELEMENTS)), "elements": elements,
            "gaps": [e for e in elements if e["status"] != "confirmed"]}


def gaps(opp):
    return inspect(opp)["gaps"]
