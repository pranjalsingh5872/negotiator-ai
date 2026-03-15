"""
orchestrator.py — Negotiation Orchestrator.

The orchestrator drives the negotiation loop:
  1. Initialises all three agents
  2. Runs each round: Buyer acts → Seller acts → Mediator evaluates
  3. Checks for agreement or termination after each round
  4. Updates shared memory with all decisions
  5. Broadcasts events to WebSocket clients

This is the "brains" of the system — it coordinates agents but does NOT
make any negotiation decisions itself. All reasoning is delegated to agents.
"""
import asyncio
import time
from typing import Optional, Callable, Awaitable

from backend.schemas import (
    NegotiationConfig, NegotiationState, AgentState, Offer, AgentAction
)
from backend.memory import NegotiationMemory
from backend.agents.buyer_agent import BuyerAgent
from backend.agents.seller_agent import SellerAgent
from backend.agents.mediator_agent import MediatorAgent


class NegotiationOrchestrator:

    def __init__(
        self,
        config: NegotiationConfig,
        broadcast_fn: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.config = config
        self.broadcast_fn = broadcast_fn

        # Initialise shared state
        state = NegotiationState(
            max_rounds=config.max_rounds,
            buyer=AgentState(
                name="BuyerAgent",
                goal=f"Buy near ${config.buyer_target:,.0f}",
                strategy="tit_for_tat",
                reservation_price=config.buyer_reservation,
                current_offer=config.buyer_target * 0.8,   # anchor below target
                concession_rate=0.06,
            ),
            seller=AgentState(
                name="SellerAgent",
                goal=f"Sell near ${config.seller_target:,.0f}",
                strategy="boulware",
                reservation_price=config.seller_reservation,
                current_offer=config.seller_target * 1.25,  # anchor above target
                concession_rate=0.04,
            ),
        )

        self.memory = NegotiationMemory(state)

        # Instantiate agents
        self.buyer = BuyerAgent(
            memory=self.memory,
            target_price=config.buyer_target,
            reservation_price=config.buyer_reservation,
        )
        self.seller = SellerAgent(
            memory=self.memory,
            target_price=config.seller_target,
            reservation_price=config.seller_reservation,
        )
        self.mediator = MediatorAgent(memory=self.memory)

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(self) -> NegotiationMemory:
        """Run the full negotiation to completion. Returns final memory."""
        print("\n" + "="*70)
        print(f"  NEGOTIATION SESSION: {self.memory.state.session_id}")
        print(f"  Product: {self.config.product}")
        print(f"  Buyer target: ${self.config.buyer_target:,.0f}  "
              f"| Reservation: ${self.config.buyer_reservation:,.0f}")
        print(f"  Seller target: ${self.config.seller_target:,.0f} "
              f"| Reservation: ${self.config.seller_reservation:,.0f}")
        print("="*70 + "\n")

        self.memory.state.status = "active"
        await self._broadcast_all_events()

        for round_num in range(1, self.config.max_rounds + 1):
            print(f"\n{'─'*60}")
            print(f"  ROUND {round_num}/{self.config.max_rounds}")
            print(f"{'─'*60}")

            self.memory.advance_round()
            self.memory.update_deadline_pressure()
            await self._broadcast_all_events()

            # ── Buyer's turn ──────────────────────────────────────────────
            buyer_action = await asyncio.to_thread(self.buyer.act)
            await self._apply_action(buyer_action, round_num)
            await self._broadcast_all_events()

            if self._check_agreement(buyer_action):
                break

            # ── Seller's turn ─────────────────────────────────────────────
            seller_action = await asyncio.to_thread(self.seller.act)
            await self._apply_action(seller_action, round_num)
            await self._broadcast_all_events()

            if self._check_agreement(seller_action):
                break

            # ── Mediator evaluates ────────────────────────────────────────
            if self.mediator.should_intervene():
                print("\n  [MEDIATOR] Deadlock detected — intervening...")
                mediator_action = await asyncio.to_thread(self.mediator.act)
                await self._apply_action(mediator_action, round_num)
                await self._broadcast_all_events()

            # ── Check for failed negotiation ──────────────────────────────
            if buyer_action.action_type == "reject" and seller_action.action_type == "reject":
                print("\n  ⚠️  Both parties rejected — negotiation failed.")
                self.memory.set_failed()
                await self._broadcast_all_events()
                break

            # Brief pause for real-time feel in demo
            await asyncio.sleep(0.5)

        # Final status
        state = self.memory.state
        if state.status == "agreed":
            print(f"\n✅  AGREEMENT REACHED: ${state.agreed_price:,.0f}")
            print(f"   Terms: {state.agreed_terms}")
        elif state.status == "failed":
            print("\n❌  NEGOTIATION FAILED — No agreement reached.")
        else:
            print("\n⏰  Max rounds reached — no agreement.")
            self.memory.set_failed()

        return self.memory

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _apply_action(self, action: AgentAction, round_num: int) -> None:
        """Convert an AgentAction into a recorded Offer and state update."""
        self.memory.record_action(action)

        if action.action_type in ("offer", "counteroffer", "mediate") and action.price:
            offer = Offer(
                round=round_num,
                agent=action.agent,
                price=action.price,
                terms=action.terms,
                reasoning=action.reasoning,
            )
            self.memory.record_offer(offer)

            # Update the agent's current_offer in state
            agent_state = getattr(self.memory.state, action.agent, None)
            if agent_state:
                agent_state.current_offer = action.price

            print(f"\n  [{action.agent.upper()}] {action.action_type.upper()}: "
                  f"${action.price:,.0f}")
            print(f"  Reasoning: {action.reasoning[:200]}")

        elif action.action_type == "accept":
            print(f"\n  [{action.agent.upper()}] ACCEPTS at ${action.price:,.0f}")

    def _check_agreement(self, action: AgentAction) -> bool:
        """Check if the latest action triggers an agreement."""
        if action.action_type != "accept" or not action.price:
            return False

        # One side accepted — check if the other side's last offer matches
        last_buyer = self.memory.get_last_offer("buyer")
        last_seller = self.memory.get_last_offer("seller")

        if not last_buyer or not last_seller:
            return False

        gap = abs(last_seller.price - last_buyer.price)
        converged_price = (last_seller.price + last_buyer.price) / 2

        # Accept if prices are within 2% of each other or one explicitly accepted
        if gap / max(last_seller.price, 1) < 0.02 or action.action_type == "accept":
            price = action.price or converged_price
            self.memory.set_agreed(
                price=price,
                terms={
                    "warranty_months": 12,
                    "delivery_days": 14,
                    "payment": "net-30",
                },
            )
            return True

        return False

    async def _broadcast_all_events(self) -> None:
        """Drain event queue and broadcast each event to WebSocket clients."""
        if not self.broadcast_fn:
            return
        for event in self.memory.drain_events():
            await self.broadcast_fn(event)
