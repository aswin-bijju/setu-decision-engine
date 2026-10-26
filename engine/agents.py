"""Stage 3: Reason. A hierarchy of specialist agents, each owning one commercial domain.

Every agent reads the shared Context and returns candidate decisions. A candidate
carries its reasoning, evidence (event ids), counter-signals, a confidence score,
EUR impact, urgency and the write-back action it would trigger if approved.
Rules are deterministic so every recommendation can be traced and audited.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from . import corridor, meddpicc
from .db import get_setting, rows

POSITIVE_KINDS = {"meeting", "usage_up", "expansion_news", "intent", "funding", "identify_pain"}
MARKET_KINDS = {"intent", "hiring", "expansion_news", "funding", "trade_news"}
LATE_STAGES = {"Proposal", "Negotiation"}


@dataclass
class Context:
    today: date
    accounts: dict
    opps: dict
    stakeholders: dict
    competitors: dict
    events: list
    strategy: dict
    fx: float

    def days_since(self, iso):
        return (self.today - date.fromisoformat(iso[:10])).days if iso else None

    def days_until(self, iso):
        return (date.fromisoformat(iso[:10]) - self.today).days

    def events_for(self, account_id=None, opp_id=None, kinds=None, days=90):
        cutoff = (self.today - timedelta(days=days)).isoformat()
        return [e for e in self.events
                if e["occurred_at"] >= cutoff
                and (account_id is None or e["account_id"] == account_id)
                and (opp_id is None or e["opportunity_id"] == opp_id)
                and (kinds is None or e["kind"] in kinds)]

    def open_opps(self):
        return [o for o in self.opps.values() if o["status"] == "open"]

    def opp_for(self, account_id):
        return next((o for o in self.open_opps() if o["account_id"] == account_id), None)

    def people(self, account_id, role=None):
        return [s for s in self.stakeholders.get(account_id, []) if role is None or s["role"] == role]

    def champion(self, account_id):
        champs = self.people(account_id, "champion")
        return champs[0] if champs else None

    def amount_eur(self, opp):
        return corridor.to_eur(opp["amount"], opp["currency"], self.fx)


def build_context(conn, today=None):
    today = today or date.today()
    stakeholders = defaultdict(list)
    for s in rows(conn, "SELECT * FROM stakeholders"):
        stakeholders[s["account_id"]].append(s)
    return Context(
        today=today,
        accounts={a["id"]: a for a in rows(conn, "SELECT * FROM accounts")},
        opps={o["id"]: o for o in rows(conn, "SELECT * FROM opportunities")},
        stakeholders=stakeholders,
        competitors={c["id"]: c for c in rows(conn, "SELECT * FROM competitors")},
        events=rows(conn, "SELECT * FROM events WHERE resolved = 1 ORDER BY occurred_at DESC"),
        strategy=get_setting(conn, "strategy", {}),
        fx=corridor.EUR_INR,
    )


def ids(events):
    return [e["id"] for e in events]


def dedupe(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def counters(events):
    return [f"{e['occurred_at']} · {e['source']}: {e['text']}" for e in events]


def close_urgency(ctx, opp):
    return max(0.15, min(1.0, 1 - ctx.days_until(opp["close_date"]) / 90))


def candidate(agent, type_, title, recommendation, *, reasoning, evidence, confidence, impact,
              urgency, account=None, opp=None, owner=None, counter=None, fit=0.5, action=None, key=None):
    return {
        "agent": agent, "type": type_, "title": title, "recommendation": recommendation,
        "account_id": account and account["id"], "opportunity_id": opp and opp["id"],
        "owner": owner or (opp and opp["owner"]),
        "key": key or f"{type_}:{(opp or account)['id']}",
        "reasoning": reasoning, "evidence": dedupe(evidence), "counter_signals": counter or [],
        "confidence": round(min(0.97, max(0.05, confidence)), 2), "impact_eur": round(impact),
        "urgency": round(urgency, 2), "strategic_fit": fit, "action": action or {},
    }


def crm_update(opp, field, value):
    return {"op": "update", "object": "Opportunity", "id": opp["id"], "field": field, "value": value}


def crm_task(owner, text, account):
    return {"op": "task", "object": "Task", "owner": owner, "text": text, "account_id": account["id"]}


# ---------------------------------------------------------------- specialists

def forecast_agent(ctx):
    """Assesses what will close and challenges commits the evidence no longer supports."""
    out = []
    for opp in ctx.open_opps():
        if opp["forecast_category"] != "commit":
            continue
        acc = ctx.accounts[opp["account_id"]]
        risk, why, ev = 0.0, [], []
        champ = ctx.champion(acc["id"])
        if champ is None:
            risk += 0.2
            why.append("No champion is recorded for this deal.")
        elif champ["status"] == "departed":
            risk += 0.35
            why.append(f"Champion {champ['name']} has left {acc['name']}.")
            ev += ids(ctx.events_for(acc["id"], kinds={"champion_departed"}))
        else:
            quiet = ctx.days_since(champ["last_engaged"])
            if quiet is not None and quiet >= 14:
                risk += 0.25
                why.append(f"Champion {champ['name']} has not engaged for {quiet} days.")
                ev += ids(ctx.events_for(acc["id"], kinds={"no_reply"}, days=30))
        if opp["close_date"] > opp["original_close_date"]:
            risk += 0.15
            why.append(f"Close date has already slipped from {opp['original_close_date']} to {opp['close_date']}.")
            ev += ids(ctx.events_for(opp_id=opp["id"], kinds={"close_date_pushed"}))
        gaps = meddpicc.gaps(opp)
        if gaps:
            risk += min(0.25, sum(0.08 if g["status"] == "missing" else 0.04 for g in gaps))
            why.append("MEDDPICC gaps: " + ", ".join(f"{g['label']} ({g['status']})" for g in gaps) + ".")
        comp = ctx.events_for(acc["id"], kinds={"competitor_mention", "competitor_hiring"}, days=30)
        if comp:
            risk += 0.15
            names = dedupe(ctx.competitors[e["competitor_id"]]["name"] for e in comp)
            why.append(f"Competitor activity in the last 30 days: {', '.join(names)}.")
            ev += ids(comp)
        usage = ctx.events_for(acc["id"], kinds={"usage_down"}, days=30)
        if usage:
            risk += 0.15
            why.append("Product usage is falling ahead of the renewal.")
            ev += ids(usage)
        pos = ctx.events_for(acc["id"], kinds=POSITIVE_KINDS, days=21)
        risk -= 0.05 * len(pos)
        if risk < 0.45:
            continue
        amount = ctx.amount_eur(opp)
        out.append(candidate(
            "Forecast", "forecast_downgrade", f"Move {acc['name']} from Commit to Best Case",
            f"Downgrade '{opp['name']}' (€{amount:,.0f}) to Best Case until the gaps below are closed. "
            f"Keep it in Commit only if {opp['owner']} can show fresh evidence this week.",
            account=acc, opp=opp, reasoning=why, evidence=ev, counter=counters(pos),
            confidence=0.45 + risk * 0.5, impact=amount, urgency=close_urgency(ctx, opp), fit=0.7,
            action={"crm": [crm_update(opp, "forecast_category", "best_case")],
                    "slack": [{"channel": "#forecast", "text": f"Setu moved {acc['name']} to Best Case. "
                               f"Owner: {opp['owner']}."}]}))
    return out


def pipeline_agent(ctx):
    """Finds deals that are drifting: no activity, overdue or repeatedly re-dated."""
    out = []
    for opp in ctx.open_opps():
        if opp["forecast_category"] == "commit":
            continue  # commits are owned by the Forecast agent
        acc = ctx.accounts[opp["account_id"]]
        idle = ctx.days_since(opp["last_activity"]) or 0
        overdue = ctx.days_until(opp["close_date"]) < 0
        slipped = opp["close_date"] > opp["original_close_date"]
        if idle < 21 and not overdue:
            continue
        why = []
        if idle >= 21:
            why.append(f"No seller or buyer activity for {idle} days.")
        if overdue:
            why.append(f"Close date {opp['close_date']} is in the past.")
        if slipped:
            why.append(f"Close date was already moved from {opp['original_close_date']}.")
        signals = ctx.events_for(acc["id"], kinds=MARKET_KINDS, days=30)
        if signals:
            why.append("The account is still showing interest in the market, so re-engaging is worth a try.")
        out.append(candidate(
            "Pipeline", "pipeline_stall", f"Re-engage or close out the stalled {acc['name']} deal",
            f"Book a re-qualification call within 5 working days. If there is no confirmed next step, "
            f"move '{opp['name']}' to Closed Lost so the pipeline stays honest.",
            account=acc, opp=opp, reasoning=why, evidence=ids(signals), counter=counters(signals),
            confidence=0.55 + min(0.3, idle / 100), impact=ctx.amount_eur(opp) * 0.5,
            urgency=0.45 + (0.2 if overdue else 0), fit=0.5,
            action={"crm": [crm_task(opp["owner"], f"Re-qualify {opp['name']} or close it out", acc)]}))
    return out


def champion_agent(ctx):
    """Tracks whether internal advocates are still engaged and whether deals are single-threaded."""
    out = []
    for acc in ctx.accounts.values():
        opp = ctx.opp_for(acc["id"])
        if not opp and not acc["is_customer"]:
            continue
        champ = ctx.champion(acc["id"])
        people = ctx.people(acc["id"])
        engaged = [s for s in people if s["status"] == "active"
                   and (ctx.days_since(s["last_engaged"]) or 999) <= 30]
        why, ev, rec = [], [], []
        if champ and champ["status"] == "departed":
            why.append(f"{champ['name']} ({champ['title']}) has left the company.")
            ev += ids(ctx.events_for(acc["id"], kinds={"champion_departed"}))
            rec.append("Ask the economic buyer to nominate a new internal owner and run a value review with them.")
        elif champ and (ctx.days_since(champ["last_engaged"]) or 0) >= 21:
            why.append(f"{champ['name']} has been quiet for {ctx.days_since(champ['last_engaged'])} days.")
            ev += ids(ctx.events_for(acc["id"], kinds={"no_reply", "meeting"}, days=30))
            rec.append(f"Have your executive sponsor contact {champ['name']} directly with a short, specific ask.")
        if len(engaged) <= 1 and (opp and ctx.amount_eur(opp) >= 100000 or acc["is_customer"]):
            why.append(f"Only {len(engaged)} stakeholder(s) engaged in the last 30 days. The deal is single-threaded.")
            rec.append("Multithread: book meetings with at least two more members of the buying committee.")
        eb = ctx.people(acc["id"], "economic_buyer")
        if opp and opp["stage"] in LATE_STAGES and (not eb or (ctx.days_since(eb[0]["last_engaged"]) or 999) > 30):
            who = eb[0]["name"] if eb else "the economic buyer"
            why.append(f"Deal is in {opp['stage']} but {who} has not been met in the last 30 days.")
            rec.append(f"Request a 30-minute meeting with {who} to confirm budget and timing.")
        if not why:
            continue
        impact = ctx.amount_eur(opp) if opp else acc["arr_eur"]
        out.append(candidate(
            "Champion", "champion_risk", f"Strengthen sponsorship at {acc['name']}", " ".join(rec),
            account=acc, opp=opp, owner=opp and opp["owner"], reasoning=why, evidence=ev,
            confidence=0.55 + 0.1 * len(why), impact=impact * 0.6,
            urgency=close_urgency(ctx, opp) if opp else 0.5, fit=0.6,
            action={"crm": [crm_task(opp["owner"] if opp else "Account owner",
                                     f"Sponsorship plan for {acc['name']}", acc)]}))
    return out


def competition_agent(ctx):
    """Watches competitor mentions and competitor hiring around our accounts."""
    out = []
    grouped = defaultdict(list)
    for e in ctx.events_for(kinds={"competitor_mention", "competitor_hiring"}, days=45):
        if e["account_id"]:
            grouped[(e["account_id"], e["competitor_id"])].append(e)
    for (acc_id, comp_id), evs in grouped.items():
        acc, comp = ctx.accounts[acc_id], ctx.competitors[comp_id]
        opp = ctx.opp_for(acc_id)
        why = [f"{len(evs)} {comp['name']} signal(s) in the last 45 days."]
        why += [f"{e['source']}: {e['text']}" for e in evs[:3]]
        why.append(f"Known positioning: {comp['positioning']}")
        champ = ctx.champion(acc_id)
        ask = champ["name"] if champ and champ["status"] == "active" else "your best contact"
        out.append(candidate(
            "Competition", "competitor_response", f"Counter {comp['name']} at {acc['name']}",
            f"Ask {ask} what the evaluation team values in {comp['name']}'s offer, then send the "
            f"{comp['name']} battle card and a reference call with a comparable EU-India customer.",
            account=acc, opp=opp, reasoning=why, evidence=ids(evs),
            confidence=0.5 + 0.1 * len(evs), impact=(ctx.amount_eur(opp) if opp else acc["arr_eur"]) * 0.5,
            urgency=0.4 + 0.15 * len(evs), fit=0.6,
            key=f"competitor_response:{acc_id}:{comp_id}",
            action={"slack": [{"channel": f"#deal-{acc_id}", "text": f"{comp['name']} is active at "
                               f"{acc['name']}. Battle card attached."}]}))
    return out


def territory_agent(ctx):
    """Spots territories where market demand is running ahead of our pipeline coverage."""
    signals, pipeline = defaultdict(list), defaultdict(float)
    for e in ctx.events_for(kinds=MARKET_KINDS, days=30):
        if e["account_id"]:
            signals[ctx.accounts[e["account_id"]]["territory"]].append(e)
    for o in ctx.open_opps():
        pipeline[ctx.accounts[o["account_id"]]["territory"]] += ctx.amount_eur(o)
    total_sig = sum(len(v) for v in signals.values()) or 1
    total_pipe = sum(pipeline.values()) or 1
    out = []
    for terr, evs in signals.items():
        sig_share, pipe_share = len(evs) / total_sig, pipeline[terr] / total_pipe
        uncovered = {e["account_id"] for e in evs if not ctx.opp_for(e["account_id"])}
        if sig_share - pipe_share < 0.15 or len(evs) < 2 or not uncovered:
            continue
        names = ", ".join(ctx.accounts[a]["name"] for a in uncovered)
        focus = terr in ctx.strategy.get("focus_territories", [])
        out.append(candidate(
            "Territory", "territory_shift", f"Shift prospecting capacity toward {terr}",
            f"Give {terr} at least one more SDR week this month and start sequences at: {names}.",
            reasoning=[f"{terr} produced {sig_share:.0%} of market signals but holds {pipe_share:.0%} of open pipeline.",
                       f"Accounts showing intent without an open deal: {names}."]
                      + (["This territory is a stated strategic focus."] if focus else []),
            evidence=ids(evs), confidence=0.5 + (sig_share - pipe_share) * 0.6,
            impact=len(uncovered) * 120000 * 0.25, urgency=0.4, fit=0.9 if focus else 0.5,
            owner="Head of Sales", key=f"territory_shift:{terr}",
            action={"slack": [{"channel": "#sales-leadership", "text": f"Demand is moving to {terr}: {names}."}]}))
    return out


def expansion_agent(ctx):
    """Finds what existing customers are likely to buy next, and which renewals need protecting."""
    out = []
    for acc in ctx.accounts.values():
        if not acc["is_customer"]:
            continue
        up = ctx.events_for(acc["id"], kinds={"usage_up"}, days=30)
        down = ctx.events_for(acc["id"], kinds={"usage_down"}, days=30)
        hiring = ctx.events_for(acc["id"], kinds={"hiring", "expansion_news"}, days=30)
        renewal = ctx.opp_for(acc["id"])
        if acc["usage_trend"] >= 0.2 or up:
            why = [f"Usage trend is +{acc['usage_trend']:.0%}."] + [e["text"] for e in up + hiring]
            out.append(candidate(
                "Expansion", "expansion_open", f"Open an expansion deal at {acc['name']}",
                "Create an expansion opportunity for additional seats and propose a corridor-wide licence "
                "covering both the EU headquarters and the India hub.",
                account=acc, owner="Account owner", reasoning=why, evidence=ids(up + hiring),
                confidence=0.6 + min(0.3, acc["usage_trend"]), impact=acc["arr_eur"] * max(0.25, acc["usage_trend"]),
                urgency=0.5, fit=0.8,
                action={"crm": [{"op": "create", "object": "Opportunity", "account_id": acc["id"],
                                 "name": f"{acc['name']} expansion", "amount": round(acc["arr_eur"] * 0.35),
                                 "currency": "EUR"}]}))
        if acc["usage_trend"] <= -0.2 or down:
            why = [f"Usage trend is {acc['usage_trend']:.0%}."] + [e["text"] for e in down]
            if renewal:
                why.append(f"Renewal '{renewal['name']}' is due on {renewal['close_date']}.")
            out.append(candidate(
                "Expansion", "renewal_risk", f"Protect the renewal at {acc['name']}",
                "Run an adoption review with the economic buyer before sending renewal paperwork, and "
                "offer a re-onboarding sprint for unused modules.",
                account=acc, opp=renewal, reasoning=why, evidence=ids(down),
                confidence=0.6 + min(0.3, -acc["usage_trend"]),
                impact=ctx.amount_eur(renewal) if renewal else acc["arr_eur"],
                urgency=close_urgency(ctx, renewal) if renewal else 0.6, fit=0.8,
                action={"crm": [crm_task(renewal["owner"] if renewal else "Account owner",
                                         f"Adoption review at {acc['name']}", acc)]}))
    return out


def corridor_agent(ctx):
    """EU-India specialist: holidays, fiscal years, FX, cross-border data and regulation."""
    out = []
    for opp in ctx.open_opps():
        acc = ctx.accounts[opp["account_id"]]
        close = date.fromisoformat(opp["close_date"])
        why, plays, ev = [], [], []
        window = corridor.slowdown_for(close, acc["region"])
        if window:
            name, start, end = window
            why.append(f"Close date {close} falls in the {name} slowdown ({start} to {end}) for a buyer in {acc['country']}.")
            plays.append(f"Pull signature forward to before {start}, or re-date to after {end}.")
        if acc["region"] == "IN":
            note = corridor.india_fiscal_note(close)
            if note:
                why.append(note)
                plays.append("Align the proposal and approval path with the Indian fiscal year end.")
        if opp["currency"] == "INR" and opp["fx_at_quote"]:
            drift = opp["fx_at_quote"] / ctx.fx - 1
            if abs(drift) >= corridor.FX_ALERT_THRESHOLD:
                quoted = opp["amount"] / opp["fx_at_quote"]
                why.append(f"EUR/INR moved from {opp['fx_at_quote']} to {ctx.fx}. The deal is now worth "
                           f"€{ctx.amount_eur(opp):,.0f} instead of the €{quoted:,.0f} quoted ({drift:+.1%}).")
                plays.append("Re-quote in EUR or add an FX adjustment clause before signature.")
        text_events = ctx.events_for(acc["id"], days=60)
        for reg_key, reg in corridor.REGULATIONS.items():
            hits = [e for e in text_events if any(k in e["text"].lower() for k in reg["keywords"])]
            industry_hit = acc["industry"] in reg.get("industries", [])
            country_ok = acc["country"] in reg.get("countries", [acc["country"]])
            if reg_key == "cbam" and industry_hit and acc["region"] == "IN":
                hits += [e for e in ctx.events_for(kinds={"regulatory_news"}, days=60)
                         if "cbam" in e["text"].lower()]
            if hits and country_ok:
                why.append(f"{reg['title']} is in play ({len(hits)} signal(s)).")
                plays.append(reg["play"])
                ev += ids(hits)
        if not why:
            continue
        out.append(candidate(
            "Corridor", "corridor_risk", f"EU-India deal check: {acc['name']}", " ".join(dedupe(plays)),
            account=acc, opp=opp, reasoning=why, evidence=ev, confidence=0.6 + 0.07 * len(why),
            impact=ctx.amount_eur(opp) * 0.4, urgency=close_urgency(ctx, opp),
            fit=0.9 if acc["corridor"] == ctx.strategy.get("focus_corridor") else 0.7,
            action={"crm": [crm_task(opp["owner"], f"Corridor checklist for {opp['name']}", acc)]}))
    return out


SPECIALISTS = [forecast_agent, pipeline_agent, champion_agent, competition_agent,
               territory_agent, expansion_agent, corridor_agent]

RISK_TYPES = {"forecast_downgrade", "pipeline_stall", "champion_risk", "competitor_response",
              "renewal_risk", "corridor_risk"}


def manager_agent(ctx, candidates):
    """Turns clusters of deal risk into coaching interventions for individual sellers."""
    by_owner = defaultdict(list)
    for c in candidates:
        if c["type"] in RISK_TYPES and c["opportunity_id"] and c["owner"]:
            by_owner[c["owner"]].append(c)
    out = []
    for owner, items in by_owner.items():
        deals = dedupe(c["opportunity_id"] for c in items)
        if len(items) < 3:
            continue
        exposure = sum(ctx.amount_eur(ctx.opps[d]) for d in deals)
        out.append(candidate(
            "Manager", "coaching", f"Run a deal review with {owner}",
            f"Hold a 45-minute deal review with {owner} this week covering "
            f"{', '.join(ctx.opps[d]['name'] for d in deals)}. Agree one next step per deal.",
            owner=owner, key=f"coaching:{owner}",
            reasoning=[f"{len(items)} risk flags across {len(deals)} deal(s) owned by {owner}."]
                      + [f"{c['agent']}: {c['title']}" for c in items],
            evidence=[e for c in items for e in c["evidence"]],
            confidence=0.7, impact=exposure * 0.2, urgency=0.6, fit=0.6,
            action={"crm": [{"op": "task", "object": "Task", "owner": "Sales manager",
                             "text": f"Deal review with {owner}", "account_id": None}]}))
    return out
