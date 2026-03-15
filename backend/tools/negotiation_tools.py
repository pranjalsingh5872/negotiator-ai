"""
negotiation_tools.py — Tool definitions passed to the Claude API.

Each tool represents a decision or analysis action an agent can take.
The LLM decides WHICH tools to call and with what arguments; the
orchestrator executes them and writes results back to shared memory.
This is the "autonomous action" part judges are looking for.
"""

NEGOTIATION_TOOLS = [
    {
        "name": "evaluate_offer",
        "description": (
            "Evaluate an incoming offer against the agent's goals, reservation price, "
            "and current market context. Returns a score and recommendation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_price": {"type": "number", "description": "The offered price to evaluate"},
                "offered_terms": {"type": "object", "description": "Non-price terms (warranty, delivery, etc.)"},
                "agent_role": {"type": "string", "enum": ["buyer", "seller", "mediator"]},
                "reservation_price": {"type": "number", "description": "Agent's walk-away price"},
                "target_price": {"type": "number", "description": "Agent's ideal price"},
                "reasoning": {"type": "string", "description": "Why this offer is good/bad"},
            },
            "required": ["offer_price", "agent_role", "reservation_price", "target_price", "reasoning"],
        },
    },
    {
        "name": "make_counteroffer",
        "description": (
            "Generate a counteroffer price using the agent's concession strategy. "
            "Takes into account deadline pressure, opponent sentiment, and round number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "current_offer": {"type": "number", "description": "Opponent's latest offer"},
                "my_last_offer": {"type": "number", "description": "Agent's previous offer"},
                "target_price": {"type": "number", "description": "Agent's goal price"},
                "reservation_price": {"type": "number", "description": "Walk-away price"},
                "deadline_pressure": {"type": "number", "description": "0=relaxed, 1=urgent"},
                "opponent_sentiment": {"type": "number", "description": "0=hostile, 1=cooperative"},
                "concession_strategy": {
                    "type": "string",
                    "enum": ["tit_for_tat", "boulware", "conceder", "problem_solving"],
                    "description": "Which concession strategy to apply",
                },
                "proposed_price": {"type": "number", "description": "The specific price you are offering"},
                "reasoning": {"type": "string", "description": "Justification for this price"},
            },
            "required": [
                "current_offer", "my_last_offer", "target_price", "reservation_price",
                "deadline_pressure", "concession_strategy", "proposed_price", "reasoning",
            ],
        },
    },
    {
        "name": "analyze_sentiment",
        "description": (
            "Analyze the tone and intent of the opponent's last message or offer. "
            "Returns cooperative vs adversarial score and detected intent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_history_summary": {"type": "string", "description": "Recent negotiation context"},
                "opponent_role": {"type": "string", "enum": ["buyer", "seller"]},
                "sentiment_score": {"type": "number", "description": "0=hostile, 1=cooperative"},
                "detected_intent": {
                    "type": "string",
                    "enum": ["anchoring", "good_faith", "bluffing", "deadline_creating", "reciprocating"],
                },
                "recommended_response": {"type": "string", "description": "How to adapt strategy"},
            },
            "required": ["offer_history_summary", "opponent_role", "sentiment_score", "detected_intent"],
        },
    },
    {
        "name": "mediate_deadlock",
        "description": (
            "Called by the Mediator when negotiation is stalled. Proposes a Pareto-efficient "
            "solution that moves both parties toward agreement."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "buyer_last_offer": {"type": "number"},
                "seller_last_offer": {"type": "number"},
                "buyer_reservation": {"type": "number"},
                "seller_reservation": {"type": "number"},
                "rounds_remaining": {"type": "number"},
                "proposed_bridge_price": {
                    "type": "number",
                    "description": "Mediator's suggested price that could unlock agreement",
                },
                "non_price_concessions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Non-price terms that could sweeten the deal",
                },
                "rationale": {"type": "string", "description": "Why this is Pareto-efficient"},
            },
            "required": [
                "buyer_last_offer", "seller_last_offer",
                "proposed_bridge_price", "rationale",
            ],
        },
    },
    {
        "name": "accept_offer",
        "description": "Signal that the agent accepts the current offer and wants to close the deal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "accepted_price": {"type": "number"},
                "justification": {"type": "string", "description": "Why accepting now is rational"},
            },
            "required": ["accepted_price", "justification"],
        },
    },
    {
        "name": "assess_walk_away",
        "description": (
            "Assess whether the agent should walk away from the negotiation entirely. "
            "Returns True if BATNA is better than the current trajectory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "best_offer_received": {"type": "number"},
                "reservation_price": {"type": "number"},
                "rounds_remaining": {"type": "number"},
                "should_walk_away": {"type": "boolean"},
                "reasoning": {"type": "string"},
            },
            "required": ["best_offer_received", "reservation_price", "should_walk_away", "reasoning"],
        },
    },
]
