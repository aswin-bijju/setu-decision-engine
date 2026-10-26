// Setu front end. Plain JavaScript, talks to the JSON API in server.py.

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const eur = (n) => "€" + Math.round(n || 0).toLocaleString("en-IE");
const pct = (n) => Math.round((n || 0) * 100) + "%";

async function api(path, body) {
  const res = await fetch("/api" + path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 3500);
}

// ---------------------------------------------------------------- tabs
const loaders = {
  decisions: loadDecisions, accounts: loadAccounts, icp: loadIcp,
  signals: loadSignals, audit: loadAudit, engine: loadEngine,
};
let current = "decisions";
$("#tabs").addEventListener("click", (e) => {
  const tab = e.target.dataset.tab;
  if (!tab) return;
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b === e.target));
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("active", s.id === "tab-" + tab));
  current = tab;
  loaders[tab]();
});

// ---------------------------------------------------------------- decision queue
async function loadDecisions() {
  const [s, list] = await Promise.all([api("/summary"), api("/decisions?status=" + $("#decision-filter").value)]);
  const st = s.last_run?.stats || {};
  $("#tiles").innerHTML = [
    ["Commit at risk", eur(s.commit_at_risk_eur), `of ${eur(s.commit_eur)} in Commit`],
    ["Decisions pending", s.pending, `${st.candidates ?? 0} considered, ${st.discarded ?? 0} discarded`],
    ["Open pipeline", eur(s.pipeline_eur), `EUR/INR ${s.eur_inr}`],
    ["Signals", s.events, s.unresolved ? `${s.unresolved} waiting for next run` : "all resolved"],
  ].map(([l, v, sub]) => `<div class="tile"><div class="label">${l}</div><div class="value">${v}</div><div class="sub">${esc(sub)}</div></div>`).join("");
  $("#briefing").textContent = s.last_run?.briefing || "Run the engine to generate a briefing.";
  $("#decisions").innerHTML = list.length ? list.map(decisionCard).join("") : `<p class="muted">Nothing here.</p>`;
}

function decisionCard(d, i) {
  const action = d.action || {};
  const isForecast = d.type === "forecast_downgrade";
  const pending = d.status === "pending";
  return `
  <div class="card decision" data-id="${d.id}">
    <div class="head">
      <div class="rank">${i + 1}</div>
      <div>
        <span class="chip ${esc(d.agent)}">${esc(d.agent)} agent</span>
        ${pending ? "" : `<span class="status ${d.status}">${d.status}</span>`}
        <div class="title">${esc(d.title)}</div>
        <div class="muted">${esc(d.account_name || d.owner || "")}</div>
      </div>
      <div class="metrics">
        <span>Impact <b>${eur(d.impact_eur)}</b></span>
        <span>Confidence <b>${pct(d.confidence)}</b></span>
        <span>Urgency <b>${pct(d.urgency)}</b></span>
      </div>
    </div>
    <div class="detail">
      <div class="rec"><b>Recommendation.</b> ${esc(d.recommendation)}</div>
      <div class="cols">
        <div>
          <h3>Why the engine thinks so</h3>
          <ul>${(d.reasoning || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
          <h3>Counter-signals</h3>
          ${(d.counter_signals || []).length ? `<ul>${d.counter_signals.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : `<p class="muted">None found.</p>`}
        </div>
        <div>
          <h3>Evidence chain</h3>
          ${d.evidence_events.length ? d.evidence_events.map((e) => `
            <div class="ev"><div class="meta">${esc(e.occurred_at)} · ${esc(e.source)} · ${esc(e.kind)}</div>${esc(e.text)}</div>`).join("")
            : `<p class="muted">Derived from CRM fields (dates, stage, MEDDPICC).</p>`}
          <h3>Write-back if approved</h3>
          <pre>${esc(JSON.stringify(action, null, 2))}</pre>
        </div>
      </div>
      ${pending ? `
      <div class="review">
        <label>Reason (required to adjust or reject; the engine learns from it)
          <textarea class="note" rows="2"></textarea></label>
        <div class="btns">
          ${isForecast ? `<select class="value"><option value="">Keep proposed value</option><option value="pipeline">Pipeline</option><option value="commit">Commit</option></select>` : ""}
          <button class="btn-approve" data-verdict="approve">Approve</button>
          <button data-verdict="adjust">Adjust</button>
          <button class="btn-reject" data-verdict="reject">Reject</button>
        </div>
      </div>` : `<p class="muted">Reviewed by ${esc(d.reviewed_by)}${d.review_note ? `: “${esc(d.review_note)}”` : ""}</p>`}
    </div>
  </div>`;
}

$("#decisions").addEventListener("click", async (e) => {
  const card = e.target.closest(".decision");
  if (!card) return;
  const verdict = e.target.dataset.verdict;
  if (!verdict) {
    if (!e.target.closest(".detail")) card.classList.toggle("open");
    return;
  }
  const note = card.querySelector(".note").value;
  const value = card.querySelector(".value")?.value || null;
  try {
    const r = await api(`/decisions/${card.dataset.id}/review`, { verdict, note, value });
    toast(`${r.status}. ${r.written_to.length ? "Written to " + r.written_to.join(", ") + ". " : ""}${r.agent} agent weight is now ${r.agent_weight}.`);
    loadDecisions();
  } catch (err) { toast(err.message); }
});
$("#decision-filter").addEventListener("change", loadDecisions);

// ---------------------------------------------------------------- accounts
async function loadAccounts() {
  const list = await api("/accounts");
  $("#account-list").innerHTML = list.map((a) => `
    <div class="item" data-id="${a.id}">
      ${a.open_decisions ? `<span class="badge">${a.open_decisions}</span>` : ""}
      <b>${esc(a.name)}</b>
      <small>${esc(a.country)} · ${esc(a.industry)} · ${a.is_customer ? "Customer" : "Prospect"} · ${esc(a.corridor)}</small>
    </div>`).join("");
}

$("#account-list").addEventListener("click", async (e) => {
  const item = e.target.closest(".item");
  if (!item) return;
  document.querySelectorAll("#account-list .item").forEach((i) => i.classList.toggle("active", i === item));
  const p = await api("/accounts/" + item.dataset.id);
  const a = p.account;
  $("#account-plan").innerHTML = `
    <div class="card">
      <h2 style="margin-top:0">${esc(a.name)}</h2>
      <p class="muted">${esc(a.industry)} · ${a.employees?.toLocaleString()} employees · ${esc(a.territory)} · Corridor ${esc(a.corridor)}
        ${a.is_customer ? ` · ARR ${eur(a.arr_eur)} · usage ${a.usage_trend > 0 ? "+" : ""}${pct(a.usage_trend)}` : ""}</p>
      <p>${esc(a.notes)}</p>
    </div>
    <div class="card"><h3>EU-India corridor context</h3>
      <p><b>Buyer norms.</b> ${esc(p.corridor.buyer_norms)}</p>
      ${p.corridor.regulations.map((r) => `<p><b>${esc(r.title)}.</b> ${esc(r.play)}</p>`).join("") || `<p class="muted">No regulatory flags.</p>`}
    </div>
    <div class="card"><h3>Buying committee ${p.committee.single_threaded ? `<span class="pill missing">single-threaded</span>` : ""}</h3>
      <table><tr><th>Role</th><th>Coverage</th><th>People</th></tr>
      ${p.committee.coverage.map((c) => `<tr><td>${esc(c.label)}</td><td><span class="pill ${c.status}">${c.status}</span></td>
        <td>${c.people.map((x) => `${esc(x.name)}, ${esc(x.title)} <span class="muted">(last engaged ${esc(x.last_engaged || "never")})</span>`).join("<br>") || "<span class='muted'>Nobody mapped</span>"}</td></tr>`).join("")}
      </table>
    </div>
    ${p.opportunities.map((o) => `
    <div class="card"><h3>${esc(o.name)}: ${eur(o.amount_eur)} · ${esc(o.stage)} · ${esc(o.forecast_category)} · closes ${esc(o.close_date)}</h3>
      <p class="muted">MEDDPICC score ${o.inspection.score}/100 · owner ${esc(o.owner)}${o.currency !== "EUR" ? ` · quoted in ${o.currency}` : ""}</p>
      <table><tr><th>Element</th><th>Status</th><th>Note</th><th>Next question</th></tr>
      ${o.inspection.elements.map((m) => `<tr><td>${esc(m.label)}</td><td><span class="pill ${m.status}">${m.status}</span></td><td>${esc(m.note)}</td><td class="muted">${esc(m.next_question)}</td></tr>`).join("")}
      </table>
    </div>`).join("")}
    <div class="card"><h3>Outreach angles and seller plays</h3>
      ${p.plays.map((x) => `<p><b>${esc(x.angle)}.</b> ${esc(x.opener)}</p>`).join("")}
    </div>
    <div class="card"><h3>Live signals</h3>
      ${p.signals.map((e) => `<div class="ev"><div class="meta">${esc(e.occurred_at)} · ${esc(e.source)} · ${esc(e.kind)}</div>${esc(e.text)}</div>`).join("") || `<p class="muted">No signals in 90 days.</p>`}
    </div>`;
});

// ---------------------------------------------------------------- ICP
async function loadIcp() {
  const list = await api("/icp");
  $("#icp").innerHTML = `<div class="card"><table>
    <tr><th>Account</th><th>Fit</th><th>Why</th><th>Suggested opener</th></tr>
    ${list.map((r) => `<tr>
      <td><b>${esc(r.account.name)}</b><br><span class="muted">${esc(r.account.country)} · ${esc(r.account.industry)} · ${esc(r.account.corridor)}</span></td>
      <td>${pct(r.score)}<div class="bar"><span style="width:${pct(r.score)}"></span></div></td>
      <td><ul style="margin:0;padding-left:1rem">${r.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></td>
      <td>${r.plays[0] ? `<b>${esc(r.plays[0].angle)}.</b> ${esc(r.plays[0].opener)}` : ""}</td>
    </tr>`).join("")}</table></div>`;
}

// ---------------------------------------------------------------- signals
async function loadSignals() {
  if (!$("#source-select").options.length) {
    $("#source-select").innerHTML = (await api("/sources")).map((s) => `<option>${s}</option>`).join("");
  }
  const evs = await api("/events");
  $("#events").innerHTML = `<div class="card"><table>
    <tr><th>Date</th><th>Source</th><th>Signal</th><th>Resolved to</th><th>Kind</th></tr>
    ${evs.map((e) => `<tr><td>${esc(e.occurred_at)}</td><td>${esc(e.source)}</td><td>${esc(e.text)}</td>
      <td>${e.resolved ? esc(e.account_name || "Market-wide") : "<span class='pill stale'>queued</span>"}</td><td>${esc(e.kind || "")}</td></tr>`).join("")}
  </table></div>`;
}

$("#signal-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  try {
    await api("/events", body);
    e.target.reset();
    toast("Signal queued. Run the engine to resolve and reason over it.");
    loadSignals();
  } catch (err) { toast(err.message); }
});

// ---------------------------------------------------------------- audit and outbox
async function loadAudit() {
  const [log, out] = await Promise.all([api("/audit"), api("/outbox")]);
  $("#audit").innerHTML = `<div class="card"><table><tr><th>Time</th><th>Actor</th><th>Action</th><th>Detail</th></tr>
    ${log.map((l) => `<tr><td>${esc(l.ts.slice(0, 19).replace("T", " "))}</td><td>${esc(l.actor)}</td><td>${esc(l.action)}${l.decision_id ? ` #${l.decision_id}` : ""}</td>
      <td class="muted">${esc(l.detail?.note || l.detail?.title || "")}</td></tr>`).join("")}</table></div>`;
  $("#outbox").innerHTML = out.length ? `<div class="card"><table><tr><th>Channel</th><th>Target</th><th>Payload</th></tr>
    ${out.map((o) => `<tr><td>${esc(o.channel)}</td><td>${esc(o.target)}</td><td><pre>${esc(JSON.stringify(o.payload, null, 1))}</pre></td></tr>`).join("")}</table></div>`
    : `<p class="muted">Nothing written yet. Approve a decision to see the CRM and Slack write-back.</p>`;
}

// ---------------------------------------------------------------- engine
async function loadEngine() {
  const s = await api("/agents");
  $("#weights").innerHTML = `<div class="card"><table><tr><th>Agent</th><th>Weight</th><th>Approved</th><th>Adjusted</th><th>Rejected</th></tr>
    ${s.weights.map((w) => `<tr><td>${esc(w.agent)}</td><td>${w.weight.toFixed(2)}<div class="bar"><span style="width:${(w.weight / 1.5) * 100}%"></span></div></td>
      <td>${w.approved}</td><td>${w.adjusted}</td><td>${w.rejected}</td></tr>`).join("")}</table></div>`;
  $("#runs").innerHTML = `<div class="card"><table><tr><th>Run</th><th>Finished</th><th>Signals resolved</th><th>Considered</th><th>Surfaced</th></tr>
    ${s.runs.map((r) => `<tr><td>#${r.id}</td><td>${esc((r.finished_at || "").slice(0, 19).replace("T", " "))}</td>
      <td>${r.stats?.events_resolved ?? ""}</td><td>${r.stats?.candidates ?? ""}</td><td>${r.stats?.surfaced ?? ""}</td></tr>`).join("")}</table></div>`;
}

// ---------------------------------------------------------------- header actions
async function busy(btn, fn) {
  btn.disabled = true;
  try { await fn(); } catch (err) { toast(err.message); } finally { btn.disabled = false; }
}
$("#btn-run").addEventListener("click", (e) => busy(e.target, async () => {
  const r = await api("/run", {});
  toast(`Run #${r.run_id}: ${r.stats.events_resolved} new signals, ${r.stats.candidates} candidates, ${r.stats.surfaced} surfaced.`);
  loaders[current]();
}));
$("#btn-simulate").addEventListener("click", (e) => busy(e.target, async () => {
  await api("/simulate", {});
  toast("Live signal ingested. Run the engine to see how it changes the queue.");
  loaders[current]();
}));
$("#btn-reset").addEventListener("click", (e) => busy(e.target, async () => {
  if (!confirm("Reload the demo data? Reviews and write-backs will be cleared.")) return;
  await api("/reset", {});
  toast("Demo data reloaded.");
  loaders[current]();
}));

loadDecisions();
