"""HTTP API and static file server. Standard library only."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from engine import accounts, corridor, meddpicc
from engine.db import connect, one, rows
from engine.ingest import SOURCES, ingest, simulate
from engine.pipeline import run_engine
from engine.review import learning_summary, review
from engine.seed import seed

WEB = Path(__file__).resolve().parent / "web"
MIME = {".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".svg": "image/svg+xml"}

conn = None
lock = threading.Lock()
ROUTES = []


def route(method, pattern):
    def wrap(fn):
        ROUTES.append((method, re.compile(f"^{pattern}$"), fn))
        return fn
    return wrap


def expand_decision(d):
    ev = d.get("evidence") or []
    if ev:
        marks = ",".join("?" * len(ev))
        d["evidence_events"] = rows(conn, f"SELECT id, source, occurred_at, text, kind FROM events "
                                          f"WHERE id IN ({marks}) ORDER BY occurred_at DESC", ev)
    else:
        d["evidence_events"] = []
    d["account_name"] = (one(conn, "SELECT name FROM accounts WHERE id = ?", (d["account_id"],)) or {}).get("name")
    return d


@route("GET", "/api/summary")
def summary(q, body):
    last = one(conn, "SELECT * FROM runs WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1")
    pending = rows(conn, "SELECT type, impact_eur FROM decisions WHERE status = 'pending'")
    opps = rows(conn, "SELECT amount, currency, forecast_category FROM opportunities WHERE status = 'open'")
    commit = sum(corridor.to_eur(o["amount"], o["currency"]) for o in opps if o["forecast_category"] == "commit")
    return {"last_run": last, "pending": len(pending),
            "commit_at_risk_eur": sum(p["impact_eur"] for p in pending if p["type"] == "forecast_downgrade"),
            "commit_eur": round(commit),
            "pipeline_eur": round(sum(corridor.to_eur(o["amount"], o["currency"]) for o in opps)),
            "events": one(conn, "SELECT COUNT(*) n FROM events")["n"],
            "unresolved": one(conn, "SELECT COUNT(*) n FROM events WHERE resolved = 0")["n"],
            "eur_inr": corridor.EUR_INR}


@route("GET", "/api/decisions")
def list_decisions(q, body):
    status = q.get("status", ["pending"])[0]
    sql = "SELECT * FROM decisions" + ("" if status == "all" else " WHERE status = ?") + \
          " ORDER BY " + ("priority DESC" if status == "pending" else "updated_at DESC") + " LIMIT 100"
    return [expand_decision(d) for d in rows(conn, sql, () if status == "all" else (status,))]


@route("GET", r"/api/decisions/(\d+)")
def get_decision(q, body, did):
    d = one(conn, "SELECT * FROM decisions WHERE id = ?", (int(did),))
    if not d:
        raise LookupError("Decision not found")
    d = expand_decision(d)
    d["audit"] = rows(conn, "SELECT * FROM audit_log WHERE decision_id = ? ORDER BY id", (int(did),))
    return d


@route("POST", r"/api/decisions/(\d+)/review")
def review_decision(q, body, did):
    return review(conn, int(did), body.get("verdict", ""), body.get("reviewer") or "leader",
                  body.get("note", ""), body.get("value") or None)


@route("POST", "/api/run")
def run(q, body):
    return run_engine(conn, use_llm=body.get("use_llm", True))


@route("GET", "/api/events")
def list_events(q, body):
    limit = int(q.get("limit", ["100"])[0])
    return rows(conn, "SELECT e.*, a.name AS account_name FROM events e LEFT JOIN accounts a "
                      "ON a.id = e.account_id ORDER BY e.occurred_at DESC, e.id DESC LIMIT ?", (limit,))


@route("POST", "/api/events")
def add_event(q, body):
    payload = {k: body[k] for k in ("email", "account") if body.get(k)}
    return {"id": ingest(conn, body.get("source", ""), body.get("text", ""), body.get("occurred_at"), payload)}


@route("POST", "/api/simulate")
def simulate_event(q, body):
    return {"id": simulate(conn)}


@route("GET", "/api/sources")
def sources(q, body):
    return SOURCES


@route("GET", "/api/accounts")
def list_accounts(q, body):
    out = rows(conn, "SELECT * FROM accounts ORDER BY is_customer DESC, name")
    for a in out:
        a["open_decisions"] = one(conn, "SELECT COUNT(*) n FROM decisions WHERE account_id = ? AND "
                                        "status = 'pending'", (a["id"],))["n"]
    return out


@route("GET", r"/api/accounts/([\w-]+)")
def get_account(q, body, aid):
    plan = accounts.account_plan(conn, aid)
    if not plan:
        raise LookupError("Account not found")
    return plan


@route("GET", "/api/icp")
def icp(q, body):
    return accounts.icp_rank(conn)


@route("GET", r"/api/opportunities/([\w-]+)/meddpicc")
def inspect(q, body, oid):
    opp = one(conn, "SELECT * FROM opportunities WHERE id = ?", (oid,))
    if not opp:
        raise LookupError("Opportunity not found")
    return meddpicc.inspect(opp)


@route("GET", "/api/audit")
def audit_log(q, body):
    return rows(conn, "SELECT * FROM audit_log ORDER BY id DESC LIMIT 200")


@route("GET", "/api/outbox")
def outbox(q, body):
    return rows(conn, "SELECT * FROM outbox ORDER BY id DESC LIMIT 200")


@route("GET", "/api/agents")
def agent_state(q, body):
    return {"weights": learning_summary(conn),
            "runs": rows(conn, "SELECT id, started_at, finished_at, stats FROM runs ORDER BY id DESC LIMIT 10")}


@route("POST", "/api/reset")
def reset(q, body):
    seed(conn)
    return run_engine(conn, use_llm=False)


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, data, ctype="application/json"):
        raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _dispatch(self, method):
        url = urlparse(self.path)
        if method == "GET" and not url.path.startswith("/api/"):
            return self._static(url.path)
        body = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._send(400, {"error": "Body must be JSON"})
        for m, pattern, fn in ROUTES:
            match = pattern.match(url.path)
            if m == method and match:
                try:
                    with lock:
                        return self._send(200, fn(parse_qs(url.query), body, *match.groups()))
                except LookupError as e:
                    return self._send(404, {"error": str(e)})
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
        self._send(404, {"error": "Not found"})

    def _static(self, path):
        f = (WEB / (path.lstrip("/") or "index.html")).resolve()
        if WEB not in f.parents or not f.is_file():
            f = WEB / "index.html"
        self._send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"))

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def log_message(self, fmt, *args):
        pass


def serve(host="127.0.0.1", port=8000, db=None, reset_data=False):
    global conn
    conn = connect(db)
    if reset_data or not one(conn, "SELECT id FROM accounts LIMIT 1"):
        seed(conn)
        run_engine(conn, use_llm=False)
    print(f"Setu is running at http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
