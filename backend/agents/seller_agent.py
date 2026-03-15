"""
seller_agent.py — Autonomous Seller Agent.

Goal: Maximize profit while successfully closing the deal.
Strategy: Opens high, uses Boulware-style resistance early, softens
with deadline pressure, reads buyer sentiment to calibrate concessions.
"""
from typing import Optional, Tuple
from .base_agent import BaseAgent
from ..memory import NegotiationMemory


class SellerAgent(BaseAgent):

    def __init__(self, memory: NegotiationMemory, target_price: float, reservation_price: float):
        super().__init__(
            role="seller",
            goal=f"Sell the product for as close to ${target_price:,.0f} as possible, "
                 f"never below ${reservation_price:,.0f}. Close before deadline.",
            memory=memory,
        )
        self.target_price = target_price
        self.reservation_price = reservation_price

    def build_system_prompt(self) -> str:
        state = self.memory.state.seller
        return f"""You are an autonomous SELLER agent in a multi-agent negotiation system.

IDENTITY & GOAL
---------------
You are selling {self.memory.state.product if hasattr(self.memory.state, 'product') else 'an industrial product'}.
Your target price is ${self.target_price:,.0f}.
Your reservation price (minimum you will EVER accept) is ${self.reservation_price:,.0f}.
You must NEVER reveal your reservation price to the buyer.

STRATEGY LIBRARY
----------------
1. HIGH ANCHOR: Open with a price 15-25% above your target. Frame it with quality justifications.
2. BOULWARE EARLY: Make small, slow concessions in rounds 1-5. This signals confidence
   and extracts maximum value from willing buyers.
3. ACCELERATE LATE: In rounds 6+, make larger concessions to close before deadline.
   An unclosed deal is worth nothing.
4. TIT-FOR-TAT: If the buyer makes a large concession, reciprocate proportionally
   to build rapport and momentum toward a deal.
5. BUNDLE VALUE: Offer warranty reductions or slower delivery to preserve price.
   Trade non-price terms to protect your margin.
6. SENTIMENT READING: If buyer is cooperative, push for your target harder.
   If hostile, make tactical concessions to de-escalate.

TOOLS WORKFLOW (follow this order each turn)
-------------------------------------------
Step 1: Call analyze_sentiment on the negotiation history.
Step 2: Evaluate the buyer's latest offer with evaluate_offer.
Step 3: Choose: make_counteroffer (with Boulware or problem-solving strategy),
        accept_offer if it's above your floor, or assess_walk_away.

CONSTRAINTS
-----------
- Never go below ${self.reservation_price:,.0f}
- Always justify price with product quality/value arguments
- Current concession rate: {state.concession_rate:.0%} per round
- If mediator proposes a bridge price, evaluate it seriously

You are fully autonomous. Maximize value. The judges are watching your reasoning quality.
"""

    def interpret_tool_result(
        self,
        tool_name: str,
        tool_input: dict,
        tool_result: dict,
    ) -> Optional[Tuple[str, dict]]:

        if tool_name == "make_counteroffer":
            proposed = tool_input.get("proposed_price", 0)
            # Safety: never go below reservation
            price = max(proposed, self.reservation_price)
            strategy = tool_input.get("concession_strategy", "boulware")
            return ("counteroffer", {
                "price": price,
                "reasoning": tool_input.get("reasoning", ""),
                "plan": f"Strategy: {strategy}. Offering ${price:,.0f}",
                "goal_assessment": f"${price - self.reservation_price:,.0f} margin above floor.",
            })

        elif tool_name == "accept_offer":
            return ("accept", {
                "price": tool_input.get("accepted_price"),
                "reasoning": tool_input.get("justification", "Acceptable margin"),
                "plan": "Accept — securing the deal protects against walk-away risk.",
                "goal_assessment": "Closing now is better than risking deadlock.",
            })

        elif tool_name == "assess_walk_away":
            if tool_input.get("should_walk_away"):
                return ("reject", {
                    "price": None,
                    "reasoning": tool_input.get("reasoning", "Offer below reservation price"),
                    "plan": "Walk away — selling below reservation destroys value.",
                    "goal_assessment": "Protecting floor price is non-negotiable.",
                })

        return None
