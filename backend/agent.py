"""Main agent graph.

Flow:
  START → check_auth
    ├─ not verified → phone_validation → END (wait for next turn)
    └─ verified     → handle_request   → END
"""
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from graphs.phone_validation import (
    PhoneValidationState,
    create_phone_validation_graph,
    _extract_phone,
)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    customer_id: str | None
    phone_verified: bool
    phone_number: str | None


def check_auth(state: AgentState) -> str:
    return "phone_validation" if not state.get("phone_verified") else "handle_request"


def merge_phone_result(state: AgentState) -> AgentState:
    """Invoke the phone validation subgraph and merge its output back."""
    subgraph = create_phone_validation_graph()
    sub_state: PhoneValidationState = {
        "messages": state["messages"],
        "customer_id": state.get("customer_id"),
        "phone_verified": state.get("phone_verified", False),
        "phone_number": state.get("phone_number"),
    }
    result = subgraph.invoke(sub_state)
    return {
        "messages": result["messages"],
        "customer_id": result.get("customer_id"),
        "phone_verified": result.get("phone_verified", False),
        "phone_number": result.get("phone_number"),
    }


def handle_request(state: AgentState) -> AgentState:
    # TODO: implement policy enforcement + tool calls
    return {"messages": [AIMessage(content="[Agent not yet implemented — policy enforcement coming soon]")]}


def create_agent() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("phone_validation", merge_phone_result)
    graph.add_node("handle_request", handle_request)
    graph.set_conditional_entry_point(
        check_auth,
        {"phone_validation": "phone_validation", "handle_request": "handle_request"},
    )
    graph.add_edge("phone_validation", END)
    graph.add_edge("handle_request", END)
    return graph.compile()


agent = create_agent()
