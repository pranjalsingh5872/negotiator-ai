#!/usr/bin/env python3
"""
run_demo.py — Hackathon Judge Demo Script

Run this to see the Multi-Agent Negotiation System in action from the CLI.
No frontend required — all agent reasoning is printed in real time.

Usage:
  python demo/run_demo.py
  python demo/run_demo.py --rounds 5 --product "Software License"

The demo runs a LIVE negotiation with real LLM calls.
Every agent decision is dynamic — the LLM reasons from scratch each round.
"""
import asyncio
import argparse
import os
import sys
import json
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from schemas import NegotiationConfig
from orchestrator import NegotiationOrchestrator


BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║          MULTI-AGENT NEGOTIATION SYSTEM  v1.0                   ║
║          Powered by Claude — Hackathon Demo                      ║
╚══════════════════════════════════════════════════════════════════╝

  Three autonomous AI agents negotiate a deal in real time.
  Every decision is made by Claude using tool calls — zero hardcoding.

  Agents:
    🔵 BUYER    — Minimize price, maximize value terms
    🔴 SELLER   — Maximize profit, close the deal
    🟡 MEDIATOR — Detect deadlocks, find Pareto-efficient solutions

  Watch the Goal → Plan → Act loop in action.
"""


def print_section(title: str, char: str = "─", width: int = 66):
    print(f"\n{char * width}")
    print(f"  {title}")
    print(char * width)


def print_offer_table(offers):
    print_section("OFFER TIMELINE")
    print(f"  {'Round':>5}  {'Agent':>10}  {'Price':>12}  {'Reasoning (truncated)'}")
    print(f"  {'─'*5}  {'─'*10}  {'─'*12}  {'─'*35}")
    for o in offers:
        reasoning_short = (o.reasoning or "")[:45].replace("\n", " ")
        print(f"  {o.round:>5}  {o.agent:>10}  ${o.price:>11,.0f}  {reasoning_short}")


def print_final_summary(memory):
    state = memory.state
    print_section("NEGOTIATION COMPLETE", char="═")

    status_icon = "✅" if state.status == "agreed" else "❌"
    print(f"\n  {status_icon}  STATUS: {state.status.upper()}")

    if state.status == "agreed":
        buyer_savings = state.buyer.reservation_price - state.agreed_price
        seller_margin = state.agreed_price - state.seller.reservation_price
        print(f"\n  Agreed Price:     ${state.agreed_price:>12,.0f}")
        print(f"  Agreed Terms:     {state.agreed_terms}")
        print(f"\n  Buyer saved:      ${buyer_savings:>12,.0f} vs reservation")
        print(f"  Seller margin:    ${seller_margin:>12,.0f} above floor")

        zopa = memory.get_zopa()
        if zopa["midpoint"]:
            deviation = abs(state.agreed_price - zopa["midpoint"])
            print(f"  ZOPA midpoint:    ${zopa['midpoint']:>12,.0f}")
            print(f"  Deviation:        ${deviation:>12,.0f} from midpoint")

    print(f"\n  Rounds used:      {state.round}/{state.max_rounds}")
    print(f"  Mediator notes:   {len(state.mediator_interventions)}")

    if state.mediator_interventions:
        print("\n  Mediator observations:")
        for note in state.mediator_interventions[-3:]:
            print(f"    • {note[:80]}")


def demonstrate_autonomy():
    print_section("WHY THIS IS AUTONOMOUS — Judge Notes")
    points = [
        "🧠 LLM reasons from SCRATCH each round — no if/else trees",
        "🔧 Tool calls (evaluate_offer, make_counteroffer, analyze_sentiment)",
        "   determine ALL pricing decisions — we never hardcode a number",
        "📊 Agents adapt to sentiment, deadline pressure, and ZOPA in real time",
        "🤝 Mediator triggers only when deadlock conditions are dynamically detected",
        "🎯 Goal → Plan → Act: each agent builds context, reasons, acts autonomously",
        "💬 Tit-for-tat, Boulware, and conceder strategies chosen by LLM per turn",
        "🔄 Multi-turn tool use: Claude calls multiple tools, sees results, refines",
    ]
    for p in points:
        print(f"  {p}")


async def main(args):
    print(BANNER)

    config = NegotiationConfig(
        product=args.product,
        buyer_target=args.buyer_target,
        buyer_reservation=args.buyer_reservation,
        seller_target=args.seller_target,
        seller_reservation=args.seller_reservation,
        max_rounds=args.rounds,
    )

    print(f"  Product:  {config.product}")
    print(f"  Buyer:    Target ${config.buyer_target:,.0f} | Max ${config.buyer_reservation:,.0f}")
    print(f"  Seller:   Target ${config.seller_target:,.0f} | Floor ${config.seller_reservation:,.0f}")
    print(f"  ZOPA:     ${ config.seller_reservation:,.0f} — ${config.buyer_reservation:,.0f}")
    print(f"  Rounds:   {config.max_rounds}")

    input("\n  Press ENTER to start the negotiation...\n")
    start_time = datetime.utcnow()

    # Run negotiation
    orchestrator = NegotiationOrchestrator(config)
    memory = await orchestrator.run()

    elapsed = (datetime.utcnow() - start_time).total_seconds()

    # Print results
    print_offer_table(memory.get_offer_history())
    print_final_summary(memory)
    demonstrate_autonomy()

    print(f"\n  Total time: {elapsed:.1f}s | LLM calls: ~{memory.state.round * 3} (3 per round)")

    # Save log
    log_path = f"/tmp/negotiation_{memory.state.session_id}.json"
    with open(log_path, "w") as f:
        json.dump(
            {
                "session": json.loads(memory.to_json()),
                "config": config.model_dump(),
            },
            f,
            indent=2,
            default=str,
        )
    print(f"\n  Full log saved to: {log_path}")
    print("\n" + "="*66 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Agent Negotiation Demo")
    parser.add_argument("--product", default="Industrial Machinery Unit")
    parser.add_argument("--buyer-target", type=float, default=8000.0)
    parser.add_argument("--buyer-reservation", type=float, default=10500.0)
    parser.add_argument("--seller-target", type=float, default=12000.0)
    parser.add_argument("--seller-reservation", type=float, default=9000.0)
    parser.add_argument("--rounds", type=int, default=8)

    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    asyncio.run(main(args))
