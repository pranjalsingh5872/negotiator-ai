"""
base_agent.py — Abstract base agent implementing the Goal → Plan → Act loop.

Every agent in the system inherits from BaseAgent and overrides:
  - build_system_prompt()  → encodes the agent's persona and goals
  - interpret_tool_result()  → converts tool output into an AgentAction

This module supports two modes:
  1. Anthropic Claude mode (requires ANTHROPIC_API_KEY)
  2. Local deterministic fallback (use LOCAL_AGENT_MODE=1 or when key missing)
"""
import os
import json
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from ..schemas import AgentAction, Offer, NegotiationState
from ..memory import NegotiationMemory

# Optional Anthropic dependency; a local fallback path exists
try:
    import anthropic
except ModuleNotFoundError:
    anthropic = None

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
LOCAL_AGENT_MODE = os.environ.get("LOCAL_AGENT_MODE", "true").lower() in ("1", "true", "yes")

client = None
if ANTHROPIC_API_KEY and anthropic:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
else:
    client = None

MODEL = "claude-sonnet-4-20250514"

# Load from tools package
import sys
sys.path.insert(0, os.path.dirname(__file__) + "/..")
from tools.negotiation_tools import NEGOTIATION_TOOLS

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"


class BaseAgent(ABC):
    """
    Abstract negotiation agent.

    The Goal → Plan → Act loop:
      1. GOAL    — set at construction; defines what winning means.
      2. PLAN    — _build_context() assembles a rich prompt describing the
                   current state. Claude's system prompt encodes the strategy.
      3. ACT     — Claude calls one or more tools to express its decision.
                   We execute those tools and translate results into an
                   AgentAction that the orchestrator records.
    """

    def __init__(self, role: str, goal: str, memory: NegotiationMemory):
        self.role = role
        self.goal = goal
        self.memory = memory

    # ── Override in subclasses ─────────────────────────────────────────────

    @abstractmethod
    def build_system_prompt(self) -> str:
        """Return the agent's persona, goals, constraints, and strategy."""

    @abstractmethod
    def interpret_tool_result(
        self,
        tool_name: str,
        tool_input: dict,
        tool_result: dict,
    ) -> Optional[Tuple[str, dict]]:
        """
        Given the tool the LLM chose and its arguments, return:
          (action_type, kwargs_for_AgentAction)
        or None if this tool doesn't produce an action.
        """

    # ── Core reasoning loop ───────────────────────────────────────────────

    def act(self) -> AgentAction:
        """
        Execute one full Goal → Plan → Act cycle.
        Returns an AgentAction describing what the agent decided to do.
        """
        if LOCAL_AGENT_MODE or not client:
            print(f"\n[LOCAL FALLBACK] {self.role.upper()} agent running deterministic logic.")
            return self._act_local()

        context = self._build_context()
        system_prompt = self.build_system_prompt()

        print(f"\n{'='*60}")
        print(f"[{self.role.upper()}] Starting reasoning cycle — Round {self.memory.get_round()}")
        print(f"Goal: {self.goal}")

        # ── PLAN: ask Claude to reason about the situation ─────────────────
        messages = [{"role": "user", "content": context}]
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=system_prompt,
            tools=NEGOTIATION_TOOLS,
            messages=messages,
        )

        print(f"[{self.role.upper()}] Claude stop_reason: {response.stop_reason}")

        action = self._process_response(response, messages)
        print(f"[{self.role.upper()}] Action: {action.action_type} @ ${action.price or 'N/A'}")
        print(f"[{self.role.upper()}] Plan: {action.plan[:120]}...")
        return action

    def _act_local(self) -> AgentAction:
        """Deterministic fallback for non-Anthropic mode."""
        state = self.memory.state
        last_buyer = self.memory.get_last_offer("buyer")
        last_seller = self.memory.get_last_offer("seller")

        def clamp(value, low, high):
            return max(low, min(high, value))

        if self.role == "buyer":
            buyer = state.buyer
            if last_seller and last_seller.price <= buyer.reservation_price:
                if last_seller.price <= buyer.current_offer * 1.08:
                    return AgentAction(
                        agent="buyer",
                        action_type="accept",
                        price=last_seller.price,
                        terms={},
                        reasoning="Local fallback buyer accepts near-target seller offer.",
                        plan="Accept when seller offer is close enough to buyer target.",
                        goal_assessment="Agreed with minimal gap and protection of reservation."
                    )
            if last_seller:
                target_step = (last_seller.price + buyer.current_offer) / 2
                proposed = clamp(target_step, buyer.current_offer, buyer.reservation_price)
            else:
                proposed = buyer.current_offer
            return AgentAction(
                agent="buyer",
                action_type="counteroffer",
                price=proposed,
                terms={"warranty_months": 12, "delivery_days": 14},
                reasoning="Local fallback buyer counteroffers based on convention.",
                plan="Concede gradually toward seller offer while preserving reservation.",
                goal_assessment="Move negotiation forward with controlled concessions."
            )

        if self.role == "seller":
            seller = state.seller
            if last_buyer and last_buyer.price >= seller.reservation_price:
                if last_buyer.price >= seller.current_offer * 0.92:
                    return AgentAction(
                        agent="seller",
                        action_type="accept",
                        price=last_buyer.price,
                        terms={},
                        reasoning="Local fallback seller accepts buyer's strong offer.",
                        plan="Accept when buyer is close enough to seller target.",
                        goal_assessment="Seal agreement while protecting seller floor."
                    )
            if last_buyer:
                target_step = (last_buyer.price + seller.current_offer) / 2
                proposed = clamp(target_step, seller.reservation_price, seller.current_offer)
            else:
                proposed = seller.current_offer
            return AgentAction(
                agent="seller",
                action_type="counteroffer",
                price=proposed,
                terms={"warranty_months": 12, "delivery_days": 14},
                reasoning="Local fallback seller counteroffers based on conventions.",
                plan="Concede gradually toward buyer while preserving margin.",
                goal_assessment="Advance negotiation while protecting reservation."
            )

        if self.role == "mediator":
            if getattr(self, "should_intervene", lambda: False)():
                if last_buyer and last_seller:
                    proposal = (last_buyer.price + last_seller.price) / 2
                else:
                    proposal = (state.buyer.current_offer + state.seller.current_offer) / 2
                proposal = clamp(proposal, state.buyer.current_offer, state.seller.current_offer)
                return AgentAction(
                    agent="mediator",
                    action_type="mediate",
                    price=proposal,
                    terms={"warranty_months": 12, "delivery_days": 14},
                    reasoning="Local fallback mediator proposes midpoint bridge value.",
                    plan="Suggest mediated compromise to unlock deadlock.",
                    goal_assessment="Enable agreement while preserving both sides' BATNAs."
                )
            return AgentAction(
                agent="mediator",
                action_type="offer",
                price=None,
                terms={},
                reasoning="No intervention needed.",
                plan="Continue monitoring buyer/seller moves.",
                goal_assessment="Do not interfere unless deadlock is identified."
            )

        return AgentAction(
            agent=self.role,
            action_type="reject",
            price=None,
            terms={},
            reasoning="Fallback default in undefined role.",
            plan="No-op.",
            goal_assessment="No action."
        )

    # ── Private helpers ───────────────────────────────────────────────────

    def _build_context(self) -> str:
        """Assemble the negotiation context injected as the user turn."""
        state = self.memory.state
        agent_state = getattr(state, self.role, None)

        last_buyer = self.memory.get_last_offer("buyer")
        last_seller = self.memory.get_last_offer("seller")
        zopa = self.memory.get_zopa()

        ctx = f"""
NEGOTIATION CONTEXT
===================
{self.memory.get_negotiation_summary()}

YOUR CURRENT STATE ({self.role.upper()})
-----------------------------------------
Goal: {self.goal}
"""
        if agent_state:
            ctx += f"""
Reservation price (walk-away): ${agent_state.reservation_price:,.0f}
Current offer on table: ${agent_state.current_offer or 'None'}
Concession rate: {agent_state.concession_rate:.0%} per round
Sentiment toward opponent: {agent_state.sentiment_score:.2f} (0=hostile, 1=cooperative)
Deadline pressure: {agent_state.deadline_pressure:.2f} (0=relaxed, 1=critical)
Rounds remaining: {state.max_rounds - state.round}
"""

        ctx += f"""
LATEST OFFERS
--------------
Buyer last offer:  ${last_buyer.price:,.0f} (Round {last_buyer.round}) — Terms: {last_buyer.terms}
Seller last offer: ${last_seller.price:,.0f} (Round {last_seller.round}) — Terms: {last_seller.terms}
""" if last_buyer and last_seller else "\nNo offers on table yet.\n"

        ctx += f"""
ZONE OF POSSIBLE AGREEMENT
---------------------------
ZOPA exists: {zopa['exists']}
"""
        if zopa["midpoint"]:
            ctx += f"Theoretical midpoint: ${zopa['midpoint']:,.0f}\n"

        ctx += """
TASK
----
Use the available tools to:
1. Analyze the current situation relative to your goals
2. Decide whether to make an offer, counteroffer, accept, or walk away
3. If making an offer, use make_counteroffer to specify your price and reasoning
4. Always call analyze_sentiment first to calibrate your response strategy

Be strategic, autonomous, and adapt your approach based on the context.
"""
        return ctx

    def _process_response(self, response, messages: list) -> AgentAction:
        """
        Handle tool_use stop reason: collect all tool calls Claude makes,
        execute them, feed results back, and extract the AgentAction.
        """
        action_type = "offer"
        price = None
        reasoning_parts = []
        plan_parts = []
        goal_assessment = ""

        # Collect any text Claude output before/between tool calls
        for block in response.content:
            if block.type == "text":
                reasoning_parts.append(block.text)

        # If Claude wants to use tools, handle the multi-turn tool loop
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input

                print(f"  → Tool call: {tool_name}")
                print(f"    Input: {json.dumps(tool_input, indent=6)[:300]}")

                # Route tool call to subclass for interpretation
                result = self.interpret_tool_result(tool_name, tool_input, {})

                if result:
                    action_type, kwargs = result
                    if "price" in kwargs:
                        price = kwargs["price"]
                    if "reasoning" in kwargs:
                        reasoning_parts.append(kwargs["reasoning"])
                    if "plan" in kwargs:
                        plan_parts.append(kwargs["plan"])
                    goal_assessment = kwargs.get("goal_assessment", "")

                # Tool result sent back to Claude (allows multi-step reasoning)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps({"status": "executed", "tool": tool_name, **tool_input}),
                })

                # Special: if accept_offer tool called, override action_type
                if tool_name == "accept_offer":
                    action_type = "accept"
                    price = tool_input.get("accepted_price")
                    reasoning_parts.append(f"ACCEPTING: {tool_input.get('justification', '')}")
                elif tool_name == "assess_walk_away" and tool_input.get("should_walk_away"):
                    action_type = "reject"

            # Feed results back and get final Claude response (optional follow-up)
            if tool_results:
                messages = messages + [
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results},
                ]
                followup = client.messages.create(
                    model=MODEL,
                    max_tokens=500,
                    system=self.build_system_prompt(),
                    tools=NEGOTIATION_TOOLS,
                    messages=messages,
                )
                for block in followup.content:
                    if hasattr(block, "text"):
                        reasoning_parts.append(block.text)

        reasoning = "\n".join(r for r in reasoning_parts if r).strip()
        plan = "\n".join(p for p in plan_parts if p).strip() or "LLM-directed strategy"
        if not goal_assessment:
            goal_assessment = f"Action serves goal: {self.goal}"

        return AgentAction(
            agent=self.role,
            action_type=action_type,
            price=price,
            reasoning=reasoning or "(no explicit reasoning text)",
            plan=plan,
            goal_assessment=goal_assessment,
        )
