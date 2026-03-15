"""
main.py — FastAPI application entry point.

Endpoints:
  POST /negotiation/start    — Start a new negotiation session
  GET  /negotiation/{id}     — Get current state
  GET  /negotiation/{id}/log — Get full action log
  WS   /ws/{session_id}      — Real-time event stream for the dashboard

The negotiation runs in an asyncio background task so the HTTP response
returns immediately and the frontend receives live updates via WebSocket.
"""
import asyncio
import json
import uuid
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.schemas import NegotiationConfig
from backend.orchestrator import NegotiationOrchestrator
from backend.memory import NegotiationMemory


# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(session_id, []).append(ws)

    def disconnect(self, session_id: str, ws: WebSocket):
        if session_id in self.active:
            self.active[session_id].remove(ws)

    async def broadcast(self, session_id: str, event: dict):
        dead = []
        for ws in self.active.get(session_id, []):
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)


manager = ConnectionManager()

# ── Active sessions registry ──────────────────────────────────────────────────

sessions: Dict[str, NegotiationMemory] = {}


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Multi-Agent Negotiation System",
    description="Autonomous agent negotiation with Claude-powered reasoning",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    product: str = "Industrial Machinery Unit"
    buyer_target: float = 8000.0
    buyer_reservation: float = 10500.0
    seller_target: float = 12000.0
    seller_reservation: float = 9000.0
    max_rounds: int = 10


@app.post("/negotiation/start")
async def start_negotiation(req: StartRequest, background_tasks: BackgroundTasks):
    """
    Start a new negotiation. Returns session_id immediately.
    The negotiation runs asynchronously; connect to /ws/{session_id} for updates.
    """
    session_id = str(uuid.uuid4())[:8]

    config = NegotiationConfig(
        product=req.product,
        buyer_target=req.buyer_target,
        buyer_reservation=req.buyer_reservation,
        seller_target=req.seller_target,
        seller_reservation=req.seller_reservation,
        max_rounds=req.max_rounds,
    )

    async def broadcast_to_session(event: dict):
        await manager.broadcast(session_id, event)

    orchestrator = NegotiationOrchestrator(config, broadcast_fn=broadcast_to_session)
    sessions[session_id] = orchestrator.memory

    # Run negotiation in background
    background_tasks.add_task(_run_negotiation, orchestrator, session_id)

    return {
        "session_id": session_id,
        "ws_url": f"ws://localhost:8000/ws/{session_id}",
        "status": "started",
        "config": config.model_dump(),
    }


async def _run_negotiation(orchestrator: NegotiationOrchestrator, session_id: str):
    """Background task: runs the full negotiation and stores final state."""
    try:
        memory = await orchestrator.run()
        sessions[session_id] = memory
    except Exception as e:
        print(f"[ERROR] Negotiation {session_id} failed: {e}")
        await manager.broadcast(session_id, {"type": "error", "payload": {"message": str(e)}})


@app.get("/negotiation/{session_id}")
async def get_negotiation(session_id: str):
    """Return current negotiation state as JSON."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    memory = sessions[session_id]
    return json.loads(memory.to_json())


@app.get("/negotiation/{session_id}/offers")
async def get_offers(session_id: str):
    """Return offer history for the session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    memory = sessions[session_id]
    return [o.model_dump(mode="json") for o in memory.get_offer_history()]


@app.get("/negotiation/{session_id}/zopa")
async def get_zopa(session_id: str):
    """Return Zone of Possible Agreement analysis."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id].get_zopa()


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Real-time WebSocket endpoint.
    Clients connect here to receive live negotiation events:
    - offer: new offer recorded
    - action: agent action taken
    - round: round advanced
    - mediator_note: mediator observation
    - agreement: deal reached
    - failed: negotiation failed
    """
    await manager.connect(session_id, websocket)
    try:
        # Send current state immediately on connect
        if session_id in sessions:
            state = json.loads(sessions[session_id].to_json())
            await websocket.send_text(json.dumps({"type": "state_sync", "payload": state}))

        # Keep connection alive
        while True:
            await websocket.receive_text()  # heartbeat / ignore client messages
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)


@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": len(sessions)}


@app.get("/")
async def root():
    return {
        "name": "Multi-Agent Negotiation System",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "start": "POST /negotiation/start",
            "state": "GET /negotiation/{id}",
            "offers": "GET /negotiation/{id}/offers",
            "websocket": "WS /ws/{id}",
        },
    }
