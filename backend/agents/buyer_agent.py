"""
buyer_agent.py — Autonomous Buyer Agent.

Goal: Minimize price while maximizing value (warranty, delivery terms).
Strategy: Anchors low, uses tit-for-tat mirroring, applies deadline
pressure near the end, analyzes seller sentiment to adapt concessions.
"""
from typing import Optional, Tuple
from .base_agent import BaseAgent
from ..memory import NegotiationMemory


class BuyerAgent(BaseAgent):

    def __init__(self, memory: NegotiationMemory, target_price: float, reservation_price: float):
        super().__init__(
            role="buyer",
            goal=f"Buy the product for as close to ${target_price:,.0f} as possible, "
                 f"never exceeding ${reservation_price:,.0f}. Maximise warranty and fast delivery.",
            memory=memory,
        )
        self.target_price = target_price
        self.reservation_price = reservation_price

    def build_system_prompt(self) -> str:
        state = self.memory.state.buyer
        return f"""You are an autonomous BUYER agent in a multi-agent negotiation system.

IDENTITY & GOAL
---------------
You are negotiating to purchase {self.memory.state.product if hasattr(self.memory.state, 'product') else 'an industrial product'}.
Your target price is ${self.target_price:,.0f}.
Your reservation price (maximum you will EVER pay) is ${self.reservation_price:,.0f}.
You must NEVER reveal your reservation price to the seller.

STRATEGY LIBRARY
----------------
1. ANCHORING: Your first offer should be 20-30% below your target to create room.
2. TIT-FOR-TAT: Match the seller's concession pace. If they concede $200, concede ~$200.
   If they hold firm, hold firm or make a tiny concession to signal good faith.
3. DEADLINE PRESSURE: Near the end (deadline_pressure > 0.7), make larger concessions
   to close the deal. Missing the deadline means walking away with nothing.
4. SENTIMENT ANALYSIS: If seller sentiment is hostile (<0.4), be firm.
   If cooperative (>0.6), reciprocate with meaningful concessions.
5. NON-PRICE WINS: Push for extended warranty, faster delivery. These have value.

TOOLS WORKFLOW (follow this order each turn)
-------------------------------------------
Step 1: Call analyze_sentiment on the latest offer history.
Step 2: Evaluate the seller's last offer with evaluate_offer.
Step 3: Decide: accept (if offer meets criteria), make_counteroffer, or assess_walk_away.

CONSTRAINTS
-----------
- Never go above ${self.reservation_price:,.0f}
- Never show desperation explicitly
- Always provide economic reasoning for your price
- Current concession rate: {state.concession_rate:.0%} per round

You are fully autonomous. Think strategically. The judges are watching your reasoning quality.
"""

    def interpret_tool_result(
        self,
        tool_name: str,
        tool_input: dict,
        tool_result: dict,
    ) -> Optional[Tuple[str, dict]]:

        if tool_name == "make_counteroffer":
            proposed = tool_input.get("proposed_price", 0)
            # Safety: never exceed reservation price
            price = min(proposed, self.reservation_price)
            strategy = tool_input.get("concession_strategy", "tit_for_tat")
            return ("counteroffer", {
                "price": price,
                "reasoning": tool_input.get("reasoning", ""),
                "plan": f"Concession strategy: {strategy}. Proposed ${price:,.0f}",
                "goal_assessment": f"Offer of ${price:,.0f} is "
                                   f"${self.reservation_price - price:,.0f} below reservation.",
            })

        elif tool_name == "accept_offer":
            return ("accept", {
                "price": tool_input.get("accepted_price"),
                "reasoning": tool_input.get("justification", "Offer meets acceptance criteria"),
                "plan": "Accept current offer — goal achieved within constraints.",
                "goal_assessment": "Closing deal saves further concessions.",
            })

        elif tool_name == "assess_walk_away":
            if tool_input.get("should_walk_away"):
                return ("reject", {
                    "price": None,
                    "reasoning": tool_input.get("reasoning", "BATNA superior"),
                    "plan": "Walk away — reservation price would be breached.",
                    "goal_assessment": "Protecting reservation price is the goal.",
                })

        return None
