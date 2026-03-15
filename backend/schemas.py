"""
schemas.py — Pydantic data models for the negotiation system.
All agent messages, offers, and state conform to these schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime
import uuid


class Offer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    round: int
    agent: Literal["buyer", "seller", "mediator"]
    price: float
    terms: dict = Field(default_factory=dict)   # warranty_months, delivery_days, etc.
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reasoning: str = ""                          # LLM chain-of-thought


class AgentState(BaseModel):
    name: str
    goal: str
    strategy: str
    reservation_price: float                    # BATNA / walk-away price
    current_offer: Optional[float] = None
    concession_rate: float = 0.05               # how much to concede per round
    sentiment_score: float = 0.5                # 0=hostile, 1=cooperative
    deadline_pressure: float = 0.0              # 0=relaxed, 1=urgent
    rounds_remaining: int = 10


class NegotiationState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: Literal["pending", "active", "agreed", "failed"] = "pending"
    round: int = 0
    max_rounds: int = 10
    offers: List[Offer] = []
    agreed_price: Optional[float] = None
    agreed_terms: Optional[dict] = None
    buyer: AgentState
    seller: AgentState
    mediator_interventions: List[str] = []
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


class NegotiationConfig(BaseModel):
    product: str = "Industrial Machinery Unit"
    buyer_target: float = 8000.0
    buyer_reservation: float = 10500.0
    seller_target: float = 12000.0
    seller_reservation: float = 9000.0
    max_rounds: int = 10
    deadline_rounds: int = 7                    # rounds before pressure kicks in


class AgentAction(BaseModel):
    agent: Literal["buyer", "seller", "mediator"]
    action_type: Literal["offer", "counteroffer", "accept", "reject", "mediate", "concede"]
    price: Optional[float] = None
    terms: dict = {}
    reasoning: str
    plan: str                                   # what the agent planned before acting
    goal_assessment: str                        # how action serves the goal
