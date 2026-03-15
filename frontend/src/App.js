import { useState, useEffect, useRef, useCallback } from "react";

const WS_URL = "ws://localhost:8000/ws";
const API_URL = "http://localhost:8000";

const AGENT_COLORS = {
  buyer: { bg: "#1a3a5c", accent: "#4a9eed", text: "#a8d4ff", label: "BUYER" },
  seller: { bg: "#3a1a1a", accent: "#ed6a4a", text: "#ffb8a8", label: "SELLER" },
  mediator: { bg: "#2a2a0a", accent: "#d4b84a", text: "#fff0a8", label: "MEDIATOR" },
};

function formatPrice(p) {
  return p != null ? `$${Number(p).toLocaleString()}` : "—";
}

function AgentCard({ role, state, lastOffer }) {
  const c = AGENT_COLORS[role];
  if (!state) return null;
  return (
    <div style={{
      background: c.bg, border: `1px solid ${c.accent}40`, borderRadius: 12,
      padding: "16px 18px", flex: 1, minWidth: 0,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <span style={{ color: c.accent, fontFamily: "monospace", fontWeight: 700, fontSize: 13, letterSpacing: 2 }}>
          {c.label}
        </span>
        <span style={{
          background: `${c.accent}22`, color: c.text, fontSize: 11, padding: "2px 8px",
          borderRadius: 20, border: `1px solid ${c.accent}40`,
        }}>
          {state.strategy || role}
        </span>
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: "#fff", fontFamily: "monospace", marginBottom: 4 }}>
        {lastOffer ? formatPrice(lastOffer.price) : "—"}
      </div>
      <div style={{ color: c.text, fontSize: 12, marginBottom: 10, opacity: 0.8 }}>
        {lastOffer ? `Round ${lastOffer.round} offer` : "No offer yet"}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <MetricRow label="Sentiment" value={`${((state.sentiment_score || 0.5) * 100).toFixed(0)}%`} color={c.text} />
        <MetricRow label="Deadline pressure" value={`${((state.deadline_pressure || 0) * 100).toFixed(0)}%`} color={c.text} />
        <MetricRow label="Reservation" value={formatPrice(state.reservation_price)} color={c.text} />
      </div>
    </div>
  );
}

function MetricRow({ label, value, color }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
      <span style={{ color: "#888" }}>{label}</span>
      <span style={{ color, fontFamily: "monospace" }}>{value}</span>
    </div>
  );
}

function OfferBar({ offer, buyerReservation, sellerReservation }) {
  const c = AGENT_COLORS[offer.agent] || AGENT_COLORS.buyer;
  const min = sellerReservation * 0.8;
  const max = buyerReservation * 1.1;
  const pct = ((offer.price - min) / (max - min)) * 100;

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ color: c.accent, fontSize: 11, fontFamily: "monospace" }}>
          R{offer.round} {c.label}
        </span>
        <span style={{ color: "#fff", fontSize: 13, fontFamily: "monospace", fontWeight: 600 }}>
          {formatPrice(offer.price)}
        </span>
      </div>
      <div style={{ background: "#ffffff11", borderRadius: 4, height: 6, position: "relative" }}>
        <div style={{
          position: "absolute", left: `${Math.max(0, Math.min(100, pct))}%`,
          transform: "translateX(-50%)", top: 0, width: 10, height: 6,
          background: c.accent, borderRadius: 3, transition: "left 0.4s ease",
        }} />
      </div>
      {offer.reasoning && (
        <div style={{ color: "#666", fontSize: 11, marginTop: 3, lineHeight: 1.4, fontStyle: "italic" }}>
          {offer.reasoning.slice(0, 120)}…
        </div>
      )}
    </div>
  );
}

function EventLog({ events }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [events]);

  return (
    <div ref={ref} style={{
      height: 200, overflowY: "auto", background: "#0a0a0a",
      borderRadius: 8, padding: "10px 12px", fontFamily: "monospace",
      fontSize: 11, border: "1px solid #222",
    }}>
      {events.length === 0 && <span style={{ color: "#444" }}>Waiting for events...</span>}
      {events.map((e, i) => {
        const c = e.agent ? AGENT_COLORS[e.agent]?.accent : "#888";
        return (
          <div key={i} style={{ marginBottom: 4, color: c || "#aaa" }}>
            <span style={{ color: "#444", marginRight: 8 }}>{e.ts}</span>
            <span style={{ color: "#666", marginRight: 6 }}>[{e.type}]</span>
            <span>{e.message}</span>
          </div>
        );
      })}
    </div>
  );
}

function ZOPAVisualizer({ buyerRes, sellerRes, offers }) {
  const min = sellerRes * 0.75;
  const max = buyerRes * 1.15;
  const range = max - min;
  const toPos = (v) => ((v - min) / range) * 100;

  const zopaExists = buyerRes >= sellerRes;
  const lastBuyer = [...offers].reverse().find(o => o.agent === "buyer");
  const lastSeller = [...offers].reverse().find(o => o.agent === "seller");

  return (
    <div>
      <div style={{ fontSize: 11, color: "#888", marginBottom: 8, display: "flex", justifyContent: "space-between" }}>
        <span>Price range</span>
        <span style={{ color: zopaExists ? "#4aed8a" : "#ed4a4a" }}>
          ZOPA: {zopaExists ? "EXISTS ✓" : "NO OVERLAP ✗"}
        </span>
      </div>
      <div style={{ position: "relative", height: 40, margin: "8px 0 16px" }}>
        <div style={{
          position: "absolute", top: 16, left: 0, right: 0,
          height: 8, background: "#111", borderRadius: 4,
        }} />
        {zopaExists && (
          <div style={{
            position: "absolute", top: 16,
            left: `${toPos(sellerRes)}%`, width: `${toPos(buyerRes) - toPos(sellerRes)}%`,
            height: 8, background: "#4aed8a30", border: "1px solid #4aed8a50", borderRadius: 2,
          }} />
        )}
        <div style={{ position: "absolute", left: `${toPos(buyerRes)}%`, top: 0, transform: "translateX(-50%)" }}>
          <div style={{ height: 40, width: 1, background: "#4a9eed50" }} />
          <div style={{ color: "#4a9eed", fontSize: 10, whiteSpace: "nowrap", marginTop: -36, marginLeft: 4 }}>
            Buyer max
          </div>
        </div>
        <div style={{ position: "absolute", left: `${toPos(sellerRes)}%`, top: 0, transform: "translateX(-50%)" }}>
          <div style={{ height: 40, width: 1, background: "#ed6a4a50" }} />
          <div style={{ color: "#ed6a4a", fontSize: 10, whiteSpace: "nowrap", marginTop: -36, marginLeft: 4 }}>
            Seller floor
          </div>
        </div>
        {lastBuyer && (
          <div style={{
            position: "absolute", top: 12,
            left: `${toPos(lastBuyer.price)}%`, transform: "translateX(-50%)",
            width: 16, height: 16, borderRadius: "50%",
            background: "#4a9eed", border: "2px solid #fff", zIndex: 2,
            transition: "left 0.5s ease",
          }} />
        )}
        {lastSeller && (
          <div style={{
            position: "absolute", top: 12,
            left: `${toPos(lastSeller.price)}%`, transform: "translateX(-50%)",
            width: 16, height: 16, borderRadius: "50%",
            background: "#ed6a4a", border: "2px solid #fff", zIndex: 2,
            transition: "left 0.5s ease",
          }} />
        )}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#555" }}>
        <span>{formatPrice(min)}</span>
        <span>{formatPrice(max)}</span>
      </div>
    </div>
  );
}

export default function App() {
  const [sessionId, setSessionId] = useState(null);
  const [state, setState] = useState(null);
  const [offers, setOffers] = useState([]);
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState("idle");
  const [config, setConfig] = useState({
    product: "Industrial Machinery Unit",
    buyer_target: 8000,
    buyer_reservation: 10500,
    seller_target: 12000,
    seller_reservation: 9000,
    max_rounds: 8,
  });
  const wsRef = useRef(null);

  const addEvent = useCallback((type, message, agent) => {
    const ts = new Date().toLocaleTimeString();
    setEvents(ev => [...ev.slice(-200), { type, message, agent, ts }]);
  }, []);

  const connectWS = useCallback((sid) => {
    if (wsRef.current) wsRef.current.close();
    const ws = new WebSocket(`${WS_URL}/${sid}`);
    wsRef.current = ws;

    ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data);
      const { type, payload } = event;

      if (type === "state_sync") {
        setState(payload);
        setOffers(payload.offers || []);
      } else if (type === "offer") {
        setOffers(o => [...o, payload]);
        addEvent("offer", `${payload.agent} → ${formatPrice(payload.price)}`, payload.agent);
      } else if (type === "round") {
        addEvent("round", `Round ${payload.round} started`, null);
      } else if (type === "agreement") {
        setStatus("agreed");
        addEvent("agreement", `✅ DEAL at ${formatPrice(payload.price)}`, null);
      } else if (type === "failed") {
        setStatus("failed");
        addEvent("failed", "❌ Negotiation failed — no agreement", null);
      } else if (type === "mediator_note") {
        addEvent("mediator", payload.note, "mediator");
      } else if (type === "action") {
        addEvent("action", `${payload.agent}: ${payload.action_type}`, payload.agent);
      }
    };

    ws.onopen = () => addEvent("system", `Connected to session ${sid}`, null);
    ws.onerror = () => addEvent("system", "WebSocket error", null);
  }, [addEvent]);

  const startNegotiation = async () => {
    setStatus("starting");
    setOffers([]);
    setEvents([]);
    setState(null);
    try {
      const res = await fetch(`${API_URL}/negotiation/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const data = await res.json();
      setSessionId(data.session_id);
      setStatus("active");
      connectWS(data.session_id);
      addEvent("system", `Session ${data.session_id} started`, null);
    } catch (e) {
      setStatus("error");
      addEvent("system", `Error: ${e.message}`, null);
    }
  };

  const lastBuyer = [...offers].reverse().find(o => o.agent === "buyer");
  const lastSeller = [...offers].reverse().find(o => o.agent === "seller");
  const currentGap = lastBuyer && lastSeller
    ? Math.abs(lastSeller.price - lastBuyer.price)
    : null;

  return (
    <div style={{
      minHeight: "100vh", background: "#050508", color: "#eee",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      padding: "0 0 40px",
    }}>
      <div style={{
        borderBottom: "1px solid #1a1a2a", padding: "18px 32px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        background: "#07070f",
      }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: 0.5 }}>
            ⚡ Multi-Agent Negotiation System
          </div>
          <div style={{ fontSize: 12, color: "#555", marginTop: 2 }}>
            Autonomous LLM agents · Goal → Plan → Act · Claude-powered
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {sessionId && (
            <span style={{ color: "#555", fontSize: 12, fontFamily: "monospace" }}>
              Session: {sessionId}
            </span>
          )}
          <span style={{
            padding: "4px 12px", borderRadius: 20, fontSize: 12, fontWeight: 600,
            background: status === "agreed" ? "#4aed8a20" : status === "active" ? "#4a9eed20" : status === "failed" ? "#ed4a4a20" : "#22222a",
            color: status === "agreed" ? "#4aed8a" : status === "active" ? "#4a9eed" : status === "failed" ? "#ed4a4a" : "#666",
            border: `1px solid ${status === "agreed" ? "#4aed8a40" : status === "active" ? "#4a9eed40" : status === "failed" ? "#ed4a4a40" : "#2a2a3a"}`,
          }}>
            {status.toUpperCase()}
          </span>
        </div>
      </div>

      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 24px 0" }}>
        <div style={{
          background: "#0a0a12", border: "1px solid #1a1a2a", borderRadius: 12,
          padding: 20, marginBottom: 20,
        }}>
          <div style={{ fontSize: 13, color: "#888", marginBottom: 14, fontWeight: 600 }}>
            NEGOTIATION CONFIG
          </div>
          <div style={{ display: "grid", gridColumns: "1fr", gap: 12 }}>
            <input
              value={config.product}
              onChange={e => setConfig(c => ({ ...c, product: e.target.value }))}
              placeholder="Product name"
              style={{
                background: "#111", border: "1px solid #2a2a3a", borderRadius: 8,
                color: "#eee", padding: "8px 12px", fontSize: 13,
              }}
            />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
              {[
                ["Buyer target", "buyer_target"],
                ["Buyer max", "buyer_reservation"],
                ["Seller target", "seller_target"],
                ["Seller floor", "seller_reservation"],
              ].map(([label, key]) => (
                <div key={key}>
                  <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>{label}</div>
                  <input
                    type="number"
                    value={config[key]}
                    onChange={e => setConfig(c => ({ ...c, [key]: Number(e.target.value) }))}
                    style={{
                      background: "#111", border: "1px solid #2a2a3a", borderRadius: 8,
                      color: "#eee", padding: "8px 10px", fontSize: 13, width: "100%", boxSizing: "border-box",
                    }}
                  />
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>Max rounds</div>
                <input
                  type="number" value={config.max_rounds}
                  onChange={e => setConfig(c => ({ ...c, max_rounds: Number(e.target.value) }))}
                  style={{
                    background: "#111", border: "1px solid #2a2a3a", borderRadius: 8,
                    color: "#eee", padding: "8px 10px", fontSize: 13, width: 90,
                  }}
                />
              </div>
              <button
                onClick={startNegotiation}
                disabled={status === "active" || status === "starting"}
                style={{
                  marginTop: 18, padding: "10px 28px", borderRadius: 8, border: "none",
                  background: status === "active" ? "#2a2a3a" : "#4a9eed",
                  color: status === "active" ? "#666" : "#fff", fontSize: 14, fontWeight: 600,
                  cursor: status === "active" ? "not-allowed" : "pointer",
                }}
              >
                {status === "starting" ? "Starting..." : status === "active" ? "Running..." : "Start Negotiation"}
              </button>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
          <AgentCard role="buyer" state={state?.buyer} lastOffer={lastBuyer} />
          <AgentCard role="mediator" state={null} lastOffer={null} />
          <AgentCard role="seller" state={state?.seller} lastOffer={lastSeller} />
        </div>

        {currentGap != null && (
          <div style={{
            background: "#0a0a12", border: "1px solid #1a1a2a", borderRadius: 12,
            padding: 20, marginBottom: 20,
          }}>
            <div style={{ fontSize: 13, color: "#888", marginBottom: 14, fontWeight: 600 }}>
              PRICE GAP — {formatPrice(currentGap)} remaining
            </div>
            <ZOPAVisualizer
              buyerRes={config.buyer_reservation}
              sellerRes={config.seller_reservation}
              offers={offers}
            />
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div style={{
            background: "#0a0a12", border: "1px solid #1a1a2a", borderRadius: 12, padding: 20,
          }}>
            <div style={{ fontSize: 13, color: "#888", marginBottom: 14, fontWeight: 600 }}>
              OFFER TIMELINE ({offers.length})
            </div>
            <div style={{ maxHeight: 340, overflowY: "auto" }}>
              {offers.length === 0 && (
                <div style={{ color: "#444", fontSize: 12 }}>No offers yet...</div>
              )}
              {offers.map((offer, i) => (
                <OfferBar
                  key={i} offer={offer}
                  buyerReservation={config.buyer_reservation}
                  sellerReservation={config.seller_reservation}
                />
              ))}
            </div>
          </div>
          <div style={{
            background: "#0a0a12", border: "1px solid #1a1a2a", borderRadius: 12, padding: 20,
          }}>
            <div style={{ fontSize: 13, color: "#888", marginBottom: 14, fontWeight: 600 }}>
              LIVE EVENT LOG
            </div>
            <EventLog events={events} />
            {state?.mediator_interventions?.length > 0 && (
              <div style={{ marginTop: 14 }}>
                <div style={{ fontSize: 11, color: "#888", marginBottom: 8 }}>MEDIATOR NOTES</div>
                {state.mediator_interventions.slice(-3).map((note, i) => (
                  <div key={i} style={{
                    background: "#2a2a0a", border: "1px solid #d4b84a30", borderRadius: 6,
                    padding: "8px 10px", fontSize: 11, color: "#d4b84a", marginBottom: 6,
                  }}>
                    {note}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {status === "agreed" && state?.agreed_price && (
          <div style={{
            marginTop: 20, background: "#0a1a0a", border: "2px solid #4aed8a60",
            borderRadius: 12, padding: 24, textAlign: "center",
          }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#4aed8a", marginBottom: 8 }}>
              ✅ DEAL REACHED: {formatPrice(state.agreed_price)}
            </div>
            <div style={{ color: "#888", fontSize: 13 }}>
              {JSON.stringify(state.agreed_terms)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
