"""
mediator_agent.py — Autonomous Mediator Agent.

Goal: Detect deadlocks and propose Pareto-efficient bridge solutions.
Strategy: Use simple rule-based deadlock trigger plus LLM-assisted proposals.
"""
from typing import Optional, Tuple
from .base_agent import BaseAgent
from ..memory import NegotiationMemory


class MediatorAgent(BaseAgent):
    def __init__(self, memory: NegotiationMemory):
        super().__init__(
            role="mediator",
            goal="Resolve deadlocks by suggesting fair middle-ground terms and prices.",
            memory=memory,
        )

    def build_system_prompt(self) -> str:
        return f"""You are an autonomous MEDIATOR agent in a multi-agent negotiation.

Your role is to propose a bridge solution when buyer and seller become stuck.
Prioritize Pareto-efficient outcomes and keep both parties above reservation prices.
- Buyer reservation: ${self.memory.state.buyer.reservation_price:,.0f}
- Seller reservation: ${self.memory.state.seller.reservation_price:,.0f}
- Buyer last offer: ${self.memory.get_last_offer('buyer').price if self.memory.get_last_offer('buyer') else 'N/A'}
- Seller last offer: ${self.memory.get_last_offer('seller').price if self.memory.get_last_offer('seller') else 'N/A'}
"""

    def interpret_tool_result(
        self,
        tool_name: str,
        tool_input: dict,
        tool_result: dict,
    ) -> Optional[Tuple[str, dict]]:

        if tool_name == "mediate_deadlock":
            proposed = tool_input.get("proposed_bridge_price")
            if proposed is None:
                return None
            # Ensure mediator suggests price inside ZOPA if possible
            price = float(proposed)
            return ("mediate", {
                "price": price,
                "reasoning": tool_input.get("rationale", "Bridge proposal to resolve deadlock"),
                "plan": f"Present bridge price ${price:,.0f} and request both sides respond.",
                "goal_assessment": "Move both agents toward agreement while respecting reservation constraints.",
            })

        if tool_name == "accept_offer":
            return ("accept", {
                "price": tool_input.get("accepted_price"),
                "reasoning": tool_input.get("justification", "Mediator proposes closing around fair price"),
                "plan": "Accept the offer in order to conclude the negotiation with agreement.",
                "goal_assessment": "Close deal quickly while respecting previous offers.",
            })

        return None

    def should_intervene(self) -> bool:
        # Simple deadlock heuristic
        if self.memory.state.status != "active":
            return False

        last_buyer = self.memory.get_last_offer("buyer")
        last_seller = self.memory.get_last_offer("seller")
        if not last_buyer or not last_seller:
            return False

        gap = abs(last_seller.price - last_buyer.price)
        rounds_remaining = self.memory.state.max_rounds - self.memory.state.round
        # intervene if gap remains large and time is running out
        return gap > 0 and (rounds_remaining <= 2 or self.memory.state.round >= self.memory.state.max_rounds // 2)

    # Inherit BaseAgent.act() to delegate decision-making to Claude with tool calls.
    # The mediator only needs a deadlock heuristic in should_intervene().
    pass
