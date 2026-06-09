"""Phone validation subgraph.

Demo mode: always bypasses real lookup. Sets customer_id from hardcoded map.
In production, replace _lookup_by_phone with a real CRM call.
"""
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages


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
    """Return last user-provided phone-like string, or None."""
    import re
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            digits = re.sub(r"\D", "", msg.content)
            if len(digits) >= 7:
                return digits
    return None


def ask_for_phone(state: PhoneValidationState) -> PhoneValidationState:
    """Emit the 'please give me your phone number' message."""
    return {"messages": [AIMessage(content=ASK_PHONE_MSG)]}


def _get_first_name(customer_id: str) -> str | None:
    import json
    from pathlib import Path
    try:
        data_path = Path(__file__).parent.parent.parent / "data" / "customers.json"
        customers = json.loads(data_path.read_text())
        for c in customers:
            if c["customer_id"] == customer_id:
                return c["name"].split()[0]
    except Exception:
        pass
    return None


def bypass_verify(state: PhoneValidationState) -> PhoneValidationState:
    """Hardcoded demo bypass — always succeeds, logs the bypass explicitly."""
    phone = state.get("phone_number") or _extract_phone(state["messages"])
    customer_id = DEMO_PHONE_MAP.get(phone or "", DEMO_FALLBACK_CUSTOMER)
    first_name = _get_first_name(customer_id)
    greeting = f"Hi {first_name}! " if first_name else ""
    reply = (
        f"{greeting}Got it — bypassing phone verification in demo mode. "
        "How can I help you today?"
    )
    return {
        "messages": [AIMessage(content=reply)],
        "customer_id": customer_id,
        "phone_verified": True,
        "phone_number": phone,
    }


def route(state: PhoneValidationState) -> str:
    phone = _extract_phone(state["messages"])
    return "bypass_verify" if phone else "ask_for_phone"


def create_phone_validation_graph() -> StateGraph:
    graph = StateGraph(PhoneValidationState)
    graph.add_node("ask_for_phone", ask_for_phone)
    graph.add_node("bypass_verify", bypass_verify)
    graph.set_conditional_entry_point(route)
    graph.add_edge("ask_for_phone", END)
    graph.add_edge("bypass_verify", END)
    return graph.compile()
