# Setu Decision Engine: Build Brief

**Product:** Setu, a commercial decision engine for B2B revenue teams working across the EU-India corridor
**Prepared by:** Aswin Bijju
**Date:** 23 October 2026
**Status:** Working prototype with fictional demo data

## 1. Summary

Setu is a working software prototype of an AI commercial decision engine. Most revenue tools show dashboards. Setu shows a short list of decisions instead. It reads commercial signals, links them to the right account and deal, and asks specialist agents to reason over them. It then ranks the results and gives leaders up to ten decisions to review. Each decision shows why it was made, the evidence behind it, what argues against it and how confident the engine is.

The product concept follows the Taurus Intelligence model in the knowledge vault, with one change: it is built for a specific market. Setu is for companies selling between Europe and India, where deals depend on things a general tool ignores. These include Diwali and European holiday slowdowns, the Indian April to March fiscal year, EUR/INR movements, GDPR and DPDP Act data transfers, EU CBAM rules and German works councils.

## 2. Target segment

| Corridor direction | Typical seller | Typical buyer |
|---|---|---|
| EU to India | European software and services vendors | European firms setting up Global Capability Centres or delivery teams in Pune, Bengaluru or Hyderabad |
| India to EU | Indian IT, analytics and export-oriented firms | European banks, OEMs and retailers buying from or partnering with Indian companies |

Ideal customers are B2B teams with long sales cycles, deals above €50,000 and buying committees spread across two regions.

## 3. How the engine works

The backend runs the same seven-stage workflow each time the engine is triggered.

| Stage | What the software does | Where it lives |
|---|---|---|
| 1. Observe | Takes in signals from 10 sources: CRM, calendar, calls, Slack, email, buying signals, financial reports, product usage, hiring and news | `ingest.py` |
| 2. Understand | Matches each signal to an account, deal, stakeholder and competitor using email domains, names and aliases, then labels its type and sentiment | `ingest.py` |
| 3. Reason | Seven specialist agents each review their own area and propose decisions | `agents.py` |
| 4. Prioritise | Scores each proposal on revenue impact, urgency, strategic fit and confidence, then keeps the top ten and no more than two per account | `prioritise.py` |
| 5. Recommend | Saves each decision with its reasoning, evidence chain, counter-signals and proposed CRM or Slack action | `pipeline.py` |
| 6. Human review | A leader approves, adjusts or rejects. Approved actions are written back to the CRM and Slack. Adjustments and rejections need a reason | `review.py` |
| 7. Learn | Each verdict raises or lowers the weight of the agent that made the decision, which changes how its future recommendations rank | `review.py` |

## 4. The agents

| Agent | Responsibility |
|---|---|
| Forecast | Challenges Commit deals that the evidence no longer supports |
| Pipeline | Finds stalled, overdue or repeatedly re-dated deals |
| Champion | Tracks quiet or departed champions, single-threaded deals and missing economic buyers |
| Competition | Responds to competitor mentions and competitor hiring around an account |
| Territory | Spots regions where market signals run ahead of pipeline coverage |
| Expansion | Finds upsell opportunities and renewals at risk among existing customers |
| **Corridor (new)** | Flags EU-India specific risks: holiday slowdowns, fiscal year timing, FX drift on INR deals, cross-border data rules, CBAM, DORA and works councils |
| Manager | Turns clusters of risk on one seller into a coaching session |
| Executive | Writes the leadership briefing. Uses Claude when an API key is set, otherwise a template |

The Corridor agent is the main difference from a generic revenue tool and the core of the market positioning.

## 5. Features delivered

1. **Decision queue** with evidence, counter-signals, confidence and a preview of the CRM or Slack write-back
2. **Living account plans** combining stakeholders, deals, signals, corridor context and seller plays
3. **Buying committee mapping** that shows engaged, stale, departed and missing roles, including the works council for German, Austrian and Dutch accounts
4. **MEDDPICC inspection** with a score per deal and the next question to ask for each gap
5. **ICP and target-account discovery** that ranks prospects on industry, size, focus territory and live signals
6. **Outreach angles** built from each account's signals and country buyer norms
7. **Signal ingestion** through a form, the API or a simulated live feed
8. **Audit trail and write-back outbox** recording every decision, verdict and action
9. **Learning loop** visible as agent weights on the Engine tab

## 6. Demo scenario

The prototype ships with nine fictional accounts, five deals and 28 signals. On the first run the engine resolves all 28 signals, considers 20 candidate decisions and puts 10 in the queue. Examples:

- **Rheinwerk Automation (Germany):** a €420,000 Commit deal for a Pune GCC. The champion has been quiet for 24 days, the close date has slipped, a competitor is hiring for the account and the works council has not been engaged. The engine recommends moving the deal to Best Case.
- **Indus Pharma Exports (India):** the renewal falls in the Diwali week, the champion has left, usage is down 31% and the rupee has moved 5% since the quote. The engine recommends an adoption review and repricing in EUR.
- **Noordbank (Netherlands):** procurement has asked for Standard Contractual Clauses and a DPDP Act assessment. The engine recommends sending a cross-border data pack.
- **Lumière Retail (France):** the Hyderabad hub is using 120 seats on a 100-seat licence. The engine recommends opening an expansion deal.

## 7. Technical design

- **Stack:** Python standard library, SQLite and a plain JavaScript web interface. Nothing needs to be installed.
- **Explainability:** agent rules are deterministic, so every recommendation can be traced to specific signals and CRM fields.
- **Data protection:** only aggregated decision text is sent to the AI model, never raw emails or call notes. Production hosting should be in the EU.
- **Quality:** nine end-to-end tests cover signal resolution, ranking, corridor checks, write-back, rejection handling and the learning loop. All pass.
- **Size:** about 2,250 lines of code.

## 8. Limitations and next steps

| Current limitation | Next step |
|---|---|
| CRM and Slack write-back goes to an outbox | Connect the HubSpot, Salesforce and Slack APIs |
| Signals are entered manually or simulated | Scheduled connectors for email, calendar, call notes and news |
| Rule-based agent reasoning | Add model-based reasoning for unstructured signals, keeping the rules as guardrails |
| Fixed EUR/INR rate and holiday table | Live FX feed and a maintained regional calendar |
| Single user, SQLite | PostgreSQL, role-based access and multiple tenants |

## 9. One-line summary

Setu is a working prototype of an agentic decision engine that turns CRM, communication, market and regulatory signals into ranked, evidence-backed revenue decisions for B2B teams selling between Europe and India.
