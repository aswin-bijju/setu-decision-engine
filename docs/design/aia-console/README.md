# AIA console update: hi-fi mockups

Open `AIA Console Update.dc.html`. Every screen is drawn at 1440 and 360. All data is fictional demo data.

## What changed

- One shell for every internal engine: the name, an engine switcher grouped by task (Approvals, Watch, Records, Decide, Research), search by record ID, the EN/DE switch, and the date and source of the last run. Each engine shows its ground layer. Three shell options: 1a two-level tabs, 1b left rail, 1c switcher menu. The other screens use 1a.
- The approvals inbox is the console's home screen. It lists every pending decision from every engine, oldest first, and each item has the same Approve, Adjust and Reject buttons. Adjust and Reject need a reason.
- The three review gates are one component used in every engine. There are two layouts, 1e stepped and 1f stacked, and every state is on 1g.
- There is one key screen per engine (1h to 1p), plus the client role message (1q to 1t) and the public scope checker (1u).
- Links between engines are text links: role message to result log entry, register row to scope checker rule, Assumption Ledger row to precedents, Setu Corridor decision to its Regulation Register row.

## New components

| Component | States | Notes |
|---|---|---|
| ApprovalItem | default, adjust (reason), reject (reason), approved, adjusted, rejected, undo | Used in the inbox, the register proposals and the briefing send approval |
| GateBar | each gate Pending, Done or Not needed | Shows Gate 1 to 3 inline |
| GateReview | stepped, stacked | Container for the three gates |
| PrecedentCard | ledger lead not yet verified, verified with evidence class, counter-case, dropped with reason | Has the six-row Same or Different comparison |
| GatePrecedents, GateScope, GateDirections | pending, done; no close precedent; approved; adjusted with reason; direction approved or not chosen | The content of Gates 1, 2 and 3 |
| RoleMessage | email, Slack, internal preview; no change this week; EN and DE | 360 first |
| SourcedFact, ReadingBlock | – | A fact with its source, date and tag; interpretation that starts with "Our reading:" or "Inference:" |
| EngineSwitcher, RecordSearch | desktop tabs, mobile disclosure open and closed | Part of the Header |

A StatusTag variant covers these, so they need no new component: verification labels, EvidenceTag (E1 to E6), gate states, agent and engine tags, Unknown, Not found and No close precedent. StatusTag has five tones: neutral, verified, attention, unreviewed (dashed) and quiet.

## Deviations from the design system

- **The AIA Stakeholder Intelligence design system was not available.** Following your answer, I lifted the tokens from the Setu October PNGs (inferred): ground #f7f7f5, surface #ffffff, text #1f2a44, muted #566074, line #d6dce2, teal #2f6f73, teal tint #e2eeee, amber #8a5a12, plus amber #c2841f, which is only used for the strike line on the routing slip. Radius is 2px and there are no shadows. The 16 components are stand-ins that carry the same names and have to be swapped for the real ones.
- **Font:** I identified Barlow from the PNGs (inferred). The mockups load it from Google Fonts only so the canvas renders. Production must self-host it, because of the rule against third-party fonts.
- **The Organic system attached to this project is not used**, at your instruction.
- **Labels:** Gate 2 uses Approve and Adjust for "confirm" and "change", so each action has one label everywhere. Setu's "Route to someone else" becomes Reroute.
- **Roles, not people:** The Setu Manager-agent calls ("deal review with" a named seller) are reframed as territory pipeline reviews. Owners and deputies are shown as roles.
- **Hover colours:** primary buttons go navy and secondary buttons go teal tint, so no new colour is introduced.

## Inferred, not taken from the sources

- The ground layer per engine: L0 Events Ledger; L1 Regulation Register and Register Watch; L2 Monitor and Literature Research; L3 Assumption Ledger; L4 Scope checker and Setu; L5 Stakeholder Briefing.
- Record ID owners: EV- Events Ledger, FTA-A Assumption Ledger, IG-2026- briefing issue, TL-FTA- Regulation Register row. MN-, LR-, SR-, SETU- and R- are new and invented.
- Evidence classes: E1 Primary legal text, E2 Official record, E3 Peer-reviewed study, E4 Press report, E5 Grey literature, E6 Unverified claim.
- Lifecycle stages (Proposal, Negotiation, Text published, Signed, Ratification, In force, Unknown), the monitor tier definitions, Pattern and Lever names, and all 27 register rows.
- The Setu pitch page was not in the repo, so nothing was taken from it.

## Open questions for Ash

1. Do you confirm the name "Setu by AIA"? I have used it everywhere.
2. Which shell: 1a, 1b or 1c? Which gate layout: 1e or 1f? Which matrix: 1k or 1l?
3. Are my ground-layer mapping, record ID prefixes and E1 to E6 definitions right?
4. Is the client view in EN and DE at launch? I designed one DE artboard (1t). Who signs off the German copy?
5. Should client results be answered with buttons in Slack and with links in email, as drawn?
6. Is Approve and Adjust acceptable in Gate 2, or do you want Confirm and Change there?
7. What are the price per verified result, the day rate and the interview fee? They are shown as [ASK ASH] placeholders.
