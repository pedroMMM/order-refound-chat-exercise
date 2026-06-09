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


def bypass_verify(state: PhoneValidationState) -> PhoneValidationState:
    """Hardcoded demo bypass — always succeeds, logs the bypass explicitly."""
    phone = state.get("phone_number") or _extract_phone(state["messages"])
    customer_id = DEMO_PHONE_MAP.get(phone or "", DEMO_FALLBACK_CUSTOMER)
    reply = (
        "Got it — bypassing phone verification in demo mode. "
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
