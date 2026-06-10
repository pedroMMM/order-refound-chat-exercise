"""Phone validation subgraph.

Demo mode: always bypasses real lookup. Sets customer_id from hardcoded map.
In production, replace _lookup_by_phone with a real CRM call.
"""

import json
import re
import time
from pathlib import Path
from typing import TypedDict, Annotated

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph


DEMO_PHONE_MAP = {
    "5551234567": "CUST-001",
    "5559876543": "CUST-002",
    "5550001111": "CUST-003",
    "5555555555": "CUST-004",
    "5552223333": "CUST-005",
    "5554445555": "CUST-006",
    "5556667777": "CUST-007",
    "5558889999": "CUST-008",
    "5551112222": "CUST-009",
    "5553334444": "CUST-010",
    "5555556666": "CUST-011",
    "5557778888": "CUST-012",
    "5559990000": "CUST-013",
    "5552229999": "CUST-014",
    "5554440000": "CUST-015",
}
DEMO_FALLBACK_CUSTOMER = "CUST-001"

ASK_PHONE_MSG = "Hi! What's your phone number so I can pull up your account?"


class PhoneValidationState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    customer_id: str | None
    phone_verified: bool
    phone_number: str | None


def _extract_phone(messages: list[BaseMessage]) -> str | None:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            digits = re.sub(r"\D", "", msg.content)
            if len(digits) >= 7:
                return digits
    return None


def _get_customer_first_name(customer_id: str) -> str | None:
    try:
        data_path = Path(__file__).parent.parent.parent / "data" / "customers.json"
        customers = json.loads(data_path.read_text())
        for c in customers:
            if c["customer_id"] == customer_id:
                return c["name"].split()[0]
    except Exception:
        pass
    return None


def _emit(payload: dict) -> None:
    try:
        import sys
        print(f"[TRACE] {json.dumps(payload)}", flush=True, file=sys.stdout)
        dispatch_custom_event("trace", payload)
    except Exception:
        pass


def ask_for_phone(state: PhoneValidationState) -> dict:
    t0 = time.time()
    _emit({"type": "node_start", "node": "ask_for_phone"})
    _emit({"type": "node_end", "node": "ask_for_phone", "duration_ms": round((time.time() - t0) * 1000)})
    return {"messages": [AIMessage(content=ASK_PHONE_MSG)]}


def bypass_verify(state: PhoneValidationState) -> dict:
    t0 = time.time()
    _emit({"type": "node_start", "node": "bypass_verify"})

    phone = state.get("phone_number") or _extract_phone(state["messages"])
    customer_id = DEMO_PHONE_MAP.get(phone or "", DEMO_FALLBACK_CUSTOMER)
    first_name = _get_customer_first_name(customer_id)
    greeting = f"Hi {first_name}! " if first_name else ""
    reply = (
        f"{greeting}Got it — bypassing phone verification in demo mode. "
        "How can I help you today?"
    )

    _emit({
        "type": "system",
        "name": "phone_verified",
        "data": {
            "customer_id": customer_id,
            "phone": phone,
            "first_name": first_name,
        },
    })
    _emit({"type": "node_end", "node": "bypass_verify", "duration_ms": round((time.time() - t0) * 1000)})

    return {
        "messages": [AIMessage(content=reply)],
        "customer_id": customer_id,
        "phone_verified": True,
        "phone_number": phone,
    }


def route(state: PhoneValidationState) -> str:
    phone = _extract_phone(state["messages"])
    return "bypass_verify" if phone else "ask_for_phone"


def create_phone_validation_graph() -> CompiledStateGraph:
    graph = StateGraph(PhoneValidationState)
    graph.add_node("ask_for_phone", ask_for_phone)
    graph.add_node("bypass_verify", bypass_verify)
    graph.set_conditional_entry_point(route)
    graph.add_edge("ask_for_phone", END)
    graph.add_edge("bypass_verify", END)
    return graph.compile()
