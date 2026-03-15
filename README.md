# Multi-Agent Negotiation System
### Hackathon Prototype — Autonomous LLM Agents

Three autonomous AI agents negotiate a deal in real time. Every decision is made dynamically by Claude using tool calls — zero hardcoded outcomes.

---

## Quick Start (Judge Demo)

```bash
# 1. (Optional) Create and activate venv because system site-packages may be locked
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Anthropic mode (cloud API)
export ANTHROPIC_API_KEY=sk-ant-...

# 4. Local fallback mode (no Anthropic key required)
export LOCAL_AGENT_MODE=1

# 5. CLI demo (no frontend needed)
python demo/run_demo.py

# 6. Full system (backend + dashboard)
cd backend && uvicorn main:app --reload
# Open frontend/src/App.jsx in your React environment
```

---

## System Architecture

```
User → React Dashboard → FastAPI → Negotiation Orchestrator
                                        ├── BuyerAgent  → Claude API (tool calls)
                                        ├── SellerAgent → Claude API (tool calls)
                                        └── MediatorAgent → Claude API (tool calls)
                                                ↑↓
                                         Shared Memory Store
```

---

## Agent Design: Goal → Plan → Act Loop

Each agent runs this loop every round:

```
1. GOAL     Encoded in system prompt — agent knows its constraints + strategy
2. PLAN     build_context() assembles full negotiation state as user message
3. ACT      Claude calls tools to express decisions:
              - analyze_sentiment()    → calibrate strategy
              - evaluate_offer()       → assess opponent's offer
              - make_counteroffer()    → compute next price
              - mediate_deadlock()     → mediator bridge proposal
              - accept_offer()         → close the deal
              - assess_walk_away()     → BATNA check
```

---

## Tools (LLM decides which to call)

| Tool | Agent | Purpose |
|------|-------|---------|
| `analyze_sentiment` | All | Detect intent: anchoring, good-faith, bluffing |
| `evaluate_offer` | All | Score offer vs goals + BATNA |
| `make_counteroffer` | Buyer, Seller | Compute price using named strategy |
| `mediate_deadlock` | Mediator | Propose Pareto-efficient bridge |
| `accept_offer` | Buyer, Seller | Signal acceptance |
| `assess_walk_away` | All | BATNA vs current trajectory |

---

## Negotiation Strategies (LLM-selected per round)

- **Boulware** — slow concessions early, signals confidence
- **Tit-for-tat** — mirror opponent's concession rate
- **Conceder** — faster concessions when deadline pressure rises
- **Problem-solving** — creative non-price terms to unlock value

---

## Autonomy Evidence for Judges

- ✅ No hardcoded offer amounts anywhere in the codebase
- ✅ Every price computed by LLM from context each round
- ✅ Strategy shifts detected and applied dynamically
- ✅ Mediator triggers only when deadlock conditions met (code-checked + LLM-validated)
- ✅ Multi-turn tool use: Claude calls multiple tools, sees results, refines action
- ✅ Sentiment analysis drives concession acceleration/deceleration
- ✅ ZOPA computation fed into every agent prompt
- ✅ Deadline pressure modifies agent behavior in real time

---

## API Endpoints

```
POST /negotiation/start     Start negotiation, returns session_id
GET  /negotiation/{id}      Current state JSON
GET  /negotiation/{id}/offers  Offer history
GET  /negotiation/{id}/zopa    ZOPA analysis
WS   /ws/{id}               Real-time event stream
GET  /docs                  Interactive API docs
```

---

## Example Output

```
══════════════════════════════════════════════════════════
  ROUND 1/8
══════════════════════════════════════════════════════════

[BUYER] Starting reasoning cycle
  → Tool call: analyze_sentiment
  → Tool call: make_counteroffer
    Input: {"proposed_price": 6800, "strategy": "conceder", ...}
  [BUYER] COUNTEROFFER: $6,800
  Reasoning: Anchoring aggressively 15% below target...

[SELLER] Starting reasoning cycle
  → Tool call: analyze_sentiment
  → Tool call: evaluate_offer
  → Tool call: make_counteroffer
    Input: {"proposed_price": 13500, "strategy": "boulware", ...}
  [SELLER] COUNTEROFFER: $13,500

──────────────────────────────────────────────────────────
  ROUND 5/8
──────────────────────────────────────────────────────────
[MEDIATOR] Deadlock detected — intervening...
  → Tool call: mediate_deadlock
    Input: {"proposed_bridge_price": 10100, "rationale": "..."}

[SELLER] ACCEPTS: $9,800

✅  AGREEMENT REACHED: $9,800
```

---

## File Structure

```
negotiation_system/
├── backend/
│   ├── main.py              FastAPI + WebSocket hub
│   ├── orchestrator.py      Negotiation control loop
│   ├── memory.py            Shared state store
│   ├── schemas.py           Pydantic models
│   ├── agents/
│   │   ├── base_agent.py    Goal→Plan→Act base class
│   │   ├── buyer_agent.py   Buyer strategy
│   │   ├── seller_agent.py  Seller strategy
│   │   └── mediator_agent.py Mediator + Pareto logic
│   └── tools/
│       └── negotiation_tools.py  6 LLM tool definitions
├── frontend/src/App.jsx     React live dashboard
├── demo/
│   ├── run_demo.py          CLI demo for judges
│   └── example_logs.json    Pre-recorded reasoning trace
└── requirements.txt
```
