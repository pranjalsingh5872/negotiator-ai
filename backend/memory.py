"""
memory.py — Shared negotiation memory.

All agents read from and write to this store.  It acts as the single source
of truth for the entire session: offer history, agent states, and mediator
observations live here and are accessible to every agent on every turn.
"""
from typing import Optional, List, Dict, Any
from backend.schemas import NegotiationState, Offer, AgentAction
from datetime import datetime
import json


class NegotiationMemory:
    """
    In-memory shared state store for one negotiation session.

    In production you'd swap the internal dicts for Redis or a database, but
    for hackathon purposes an in-process store is simpler and fast enough.
    """

    def __init__(self, state: NegotiationState):
        self._state = state
        self._action_log: List[AgentAction] = []
        self._events: List[Dict[str, Any]] = []     # broadcast queue for WebSocket

    # ── State access ──────────────────────────────────────────────────────────

    @property
    def state(self) -> NegotiationState:
        return self._state

    def get_offer_history(self) -> List[Offer]:
        return self._state.offers

    def get_last_offer(self, agent: Optional[str] = None) -> Optional[Offer]:
        offers = self._state.offers
        if agent:
            offers = [o for o in offers if o.agent == agent]
        return offers[-1] if offers else None

    def get_round(self) -> int:
        return self._state.round

    def get_zopa(self) -> Dict[str, float]:
        """Zone of Possible Agreement: price range where both sides can agree."""
        buyer_max = self._state.buyer.reservation_price
        seller_min = self._state.seller.reservation_price
        if buyer_max >= seller_min:
            return {"lower": seller_min, "upper": buyer_max, "exists": True,
                    "midpoint": (seller_min + buyer_max) / 2}
        return {"lower": seller_min, "upper": buyer_max, "exists": False,
                "midpoint": None}

    def get_negotiation_summary(self) -> str:
        """Human-readable summary injected into each LLM prompt."""
        h = self._state.offers
        zopa = self.get_zopa()
        lines = [
            f"Session: {self._state.session_id}",
            f"Round: {self._state.round}/{self._state.max_rounds}",
            f"Status: {self._state.status}",
            f"ZOPA exists: {zopa['exists']}",
        ]
        if zopa["midpoint"]:
            lines.append(f"Theoretical midpoint: ${zopa['midpoint']:.0f}")
        if h:
            lines.append("\nOffer history:")
            for o in h[-5:]:     # last 5 offers only to keep prompt short
                lines.append(
                    f"  Round {o.round} | {o.agent.upper():8s} | "
                    f"${o.price:,.0f} | {o.terms}"
                )
        return "\n".join(lines)

    # ── State mutations ───────────────────────────────────────────────────────

    def record_offer(self, offer: Offer) -> None:
        self._state.offers.append(offer)
        self._emit_event("offer", offer.model_dump(mode="json"))

    def record_action(self, action: AgentAction) -> None:
        self._action_log.append(action)
        self._emit_event("action", action.model_dump(mode="json"))

    def advance_round(self) -> None:
        self._state.round += 1
        self._emit_event("round", {"round": self._state.round})

    def set_agreed(self, price: float, terms: dict) -> None:
        self._state.status = "agreed"
        self._state.agreed_price = price
        self._state.agreed_terms = terms
        self._state.ended_at = datetime.utcnow()
        self._emit_event("agreement", {"price": price, "terms": terms})

    def set_failed(self) -> None:
        self._state.status = "failed"
        self._state.ended_at = datetime.utcnow()
        self._emit_event("failed", {})

    def add_mediator_note(self, note: str) -> None:
        self._state.mediator_interventions.append(note)
        self._emit_event("mediator_note", {"note": note})

    def update_agent_sentiment(self, agent: str, score: float) -> None:
        target = getattr(self._state, agent)
        target.sentiment_score = max(0.0, min(1.0, score))

    def update_deadline_pressure(self) -> None:
        r = self._state.round
        max_r = self._state.max_rounds
        pressure = min(1.0, r / max_r)
        self._state.buyer.deadline_pressure = pressure
        self._state.seller.deadline_pressure = pressure

    # ── Event queue (WebSocket broadcast) ────────────────────────────────────

    def _emit_event(self, event_type: str, payload: dict) -> None:
        self._events.append({
            "type": event_type,
            "payload": payload,
            "ts": datetime.utcnow().isoformat(),
        })

    def drain_events(self) -> List[Dict[str, Any]]:
        """Pop all pending events for the WebSocket broadcaster."""
        events, self._events = self._events, []
        return events

    def to_json(self) -> str:
        return self._state.model_dump_json(indent=2)
