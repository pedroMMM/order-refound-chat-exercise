"""Main agent graph — deterministic state machine.

State machine flow (re-evaluated after every node):

  not phone_verified      → phone_validation (subgraph)
  no customer_profile     → get_customer_profile
  no intent               → classify_intent  (LLM: extract intent + order_id)
  refund + order + no elig→ check_policy
  eligible + no action    → process_refund
  escalate + no action    → do_escalate
  denied   + no action    → do_deny
  otherwise               → generate_response (LLM: write reply)
  response written        → END

LLM used in exactly 2 nodes: classify_intent, generate_response.
All routing is deterministic state checks.
All trace events via emit() → dispatch_custom_event("trace", payload).
"""

import json
import time
from pathlib import Path
from typing import Hashable, NotRequired

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.graph.state import CompiledStateGraph

from graphs.phone_validation import create_phone_validation_graph
import tools as crm


POLICY = (Path(__file__).parent.parent / "data" / "refund_policy.txt").read_text()

_llm = None
_llm_json = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-5.4-mini", temperature=0)
    return _llm


def get_llm_json():
    global _llm_json
    if _llm_json is None:
        _llm_json = ChatOpenAI(model="gpt-5.4-mini", temperature=0).bind(
            response_format={"type": "json_object"}
        )
    return _llm_json


def emit(payload: dict) -> None:
    try:
        print(f"[TRACE] {json.dumps(payload)}", flush=True)
        dispatch_custom_event("trace", payload)
    except Exception:
        pass


# ── state ─────────────────────────────────────────────────────────────────────


class AgentState(MessagesState):
    session_id: NotRequired[str]
    # persistent across turns
    customer_id: NotRequired[str | None]
    phone_verified: NotRequired[bool]
    phone_number: NotRequired[str | None]
    customer_profile: NotRequired[dict | None]
    # per-turn (reset in main.py before each message)
    order_id: NotRequired[str | None]
    intent: NotRequired[str | None]  # refund_request | inquiry | other
    eligibility: NotRequired[
        dict | None
    ]  # {decision: eligible|denied|escalate, reason: str}
    action_taken: NotRequired[str | None]  # processed | denied | escalated


# ── helpers ───────────────────────────────────────────────────────────────────


def _get_first_name(customer_id: str | None) -> str | None:
    if not customer_id:
        return None
    try:
        data = json.loads(
            (Path(__file__).parent.parent / "data" / "customers.json").read_text()
        )
        for c in data:
            if c["customer_id"] == customer_id:
                return c["name"].split()[0]
    except Exception:
        pass
    return None


def _conversation_text(state: AgentState) -> str:
    lines = []
    for m in state["messages"]:
        if isinstance(m, HumanMessage):
            lines.append(f"Customer: {m.content}")
        elif isinstance(m, AIMessage) and m.content:
            lines.append(f"Agent: {m.content}")
    return "\n".join(lines[-10:])  # last 10 exchanges


# ── routing ───────────────────────────────────────────────────────────────────


def router(state: AgentState) -> str:
    if not state.get("phone_verified"):
        dest = "phone_validation"
        reason = "Phone not verified"

    elif not state.get("customer_profile"):
        dest = "get_customer_profile"
        reason = "Need customer profile"

    elif not state.get("intent"):
        dest = "classify_intent"
        reason = "Need to understand request"

    elif (
        state.get("intent") == "refund_request"
        and state.get("order_id")
        and not state.get("eligibility")
    ):
        dest = "check_policy"
        reason = f"Checking eligibility for {state.get('order_id')}"

    elif state.get("eligibility") and not state.get("action_taken"):
        eligibility = state.get("eligibility") or {}
        decision = eligibility.get("decision")
        if decision == "eligible":
            dest = "process_refund"
            reason = "Order eligible — processing refund"
        elif decision == "escalate":
            dest = "do_escalate"
            reason = "Order exceeds threshold — escalating"
        else:
            dest = "do_deny"
            reason = f"Order ineligible: {eligibility.get('reason', '')}"

    else:
        dest = "generate_response"
        reason = "Ready to respond"

    emit({"type": "routing", "from": "router", "to": dest, "reason": reason})
    return dest


# ── nodes ─────────────────────────────────────────────────────────────────────



def node_get_customer_profile(state: AgentState) -> dict:
    t0 = time.time()
    emit({"type": "node_start", "node": "get_customer_profile"})

    customer_id = state.get("customer_id") or ""
    profile = crm.get_customer(customer_id)
    emit(
        {
            "type": "tool_call",
            "name": "get_customer",
            "input": {"customer_id": customer_id},
        }
    )
    emit({"type": "tool_result", "name": "get_customer", "output": profile})
    emit(
        {
            "type": "node_end",
            "node": "get_customer_profile",
            "duration_ms": round((time.time() - t0) * 1000),
        }
    )

    return {"customer_profile": profile}


def node_classify_intent(state: AgentState) -> dict:
    t0 = time.time()
    emit({"type": "node_start", "node": "classify_intent"})

    profile = state.get("customer_profile") or {}
    order_ids = profile.get("order_ids", [])
    conversation = _conversation_text(state)

    prompt = f"""Analyze this customer conversation and extract:
1. intent: one of "refund_request", "inquiry", "other"
2. order_id: the specific order ID mentioned (from {order_ids}), or null if none mentioned

Respond with JSON only: {{"intent": "...", "order_id": "..." or null}}

Conversation:
{conversation}"""

    response = get_llm_json().invoke([HumanMessage(content=prompt)])
    try:
        content = response.content if isinstance(response.content, str) else ""
        parsed = json.loads(content)
    except Exception:
        parsed = {"intent": "other", "order_id": None}

    emit(
        {
            "type": "llm_reasoning",
            "content": f"Intent: {parsed.get('intent')}, Order: {parsed.get('order_id')}",
            "tool_calls_planned": [],
        }
    )
    emit(
        {
            "type": "node_end",
            "node": "classify_intent",
            "duration_ms": round((time.time() - t0) * 1000),
        }
    )

    return {
        "intent": parsed.get("intent", "other"),
        "order_id": parsed.get("order_id"),
    }


def node_check_policy(state: AgentState) -> dict:
    t0 = time.time()
    emit({"type": "node_start", "node": "check_policy"})

    order_id = state.get("order_id") or ""
    result = crm.check_refund_eligibility(order_id)
    emit(
        {
            "type": "tool_call",
            "name": "check_refund_eligibility",
            "input": {"order_id": order_id},
        }
    )
    emit({"type": "tool_result", "name": "check_refund_eligibility", "output": result})
    emit(
        {
            "type": "node_end",
            "node": "check_policy",
            "duration_ms": round((time.time() - t0) * 1000),
        }
    )

    return {"eligibility": result}


def node_process_refund(state: AgentState) -> dict:
    t0 = time.time()
    emit({"type": "node_start", "node": "process_refund"})

    order_id = state.get("order_id") or ""
    result = crm.process_refund(order_id)
    emit(
        {
            "type": "tool_call",
            "name": "process_refund",
            "input": {"order_id": order_id},
        }
    )
    emit({"type": "tool_result", "name": "process_refund", "output": result})
    emit(
        {
            "type": "node_end",
            "node": "process_refund",
            "duration_ms": round((time.time() - t0) * 1000),
        }
    )

    return {"action_taken": "processed"}


def node_do_escalate(state: AgentState) -> dict:
    t0 = time.time()
    emit({"type": "node_start", "node": "do_escalate"})

    order_id = state.get("order_id") or ""
    reason = (state.get("eligibility") or {}).get(
        "reason", "Order exceeds refund threshold"
    )
    result = crm.escalate_to_human(order_id, reason)
    emit(
        {
            "type": "tool_call",
            "name": "escalate_to_human",
            "input": {"order_id": order_id, "reason": reason},
        }
    )
    emit({"type": "tool_result", "name": "escalate_to_human", "output": result})
    emit(
        {
            "type": "node_end",
            "node": "do_escalate",
            "duration_ms": round((time.time() - t0) * 1000),
        }
    )

    return {"action_taken": "escalated"}


def node_do_deny(_state: AgentState) -> dict:
    t0 = time.time()
    emit({"type": "node_start", "node": "do_deny"})
    emit(
        {
            "type": "node_end",
            "node": "do_deny",
            "duration_ms": round((time.time() - t0) * 1000),
        }
    )
    return {"action_taken": "denied"}


def node_generate_response(state: AgentState) -> dict:
    t0 = time.time()
    emit({"type": "node_start", "node": "generate_response"})

    first_name = _get_first_name(state.get("customer_id"))
    name_note = (
        f"The customer's name is {first_name}. Address them by name."
        if first_name
        else ""
    )

    context_parts = [f"REFUND POLICY:\n{POLICY}", name_note]

    if customer_profile := state.get("customer_profile"):
        context_parts.append(f"Customer profile: {json.dumps(customer_profile)}")
    if order_id := state.get("order_id"):
        order = crm.get_order(order_id)
        context_parts.append(f"Order details: {json.dumps(order)}")
    if eligibility := state.get("eligibility"):
        context_parts.append(f"Eligibility check result: {json.dumps(eligibility)}")
    if action_taken := state.get("action_taken"):
        context_parts.append(f"Action taken: {action_taken}")

    system = "\n\n".join(p for p in context_parts if p)
    conversation = [SystemMessage(content=system)] + state["messages"]

    response = get_llm().invoke(conversation)

    if usage := getattr(response, "usage_metadata", None):
        emit({
            "type": "token_usage",
            "node": "generate_response",
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        })

    emit(
        {"type": "llm_reasoning", "content": response.content, "tool_calls_planned": []}
    )
    emit(
        {
            "type": "node_end",
            "node": "generate_response",
            "duration_ms": round((time.time() - t0) * 1000),
        }
    )

    return {"messages": [AIMessage(content=response.content)]}


# ── graph assembly ────────────────────────────────────────────────────────────


def create_agent() -> CompiledStateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("phone_validation", create_phone_validation_graph())

    other_nodes = {
        "get_customer_profile": node_get_customer_profile,
        "classify_intent": node_classify_intent,
        "check_policy": node_check_policy,
        "process_refund": node_process_refund,
        "do_escalate": node_do_escalate,
        "do_deny": node_do_deny,
        "generate_response": node_generate_response,
    }
    for name, fn in other_nodes.items():
        graph.add_node(name, fn)

    all_nodes = ["phone_validation"] + list(other_nodes.keys())
    routing_targets: dict[Hashable, str] = {n: n for n in all_nodes}

    graph.set_conditional_entry_point(router, routing_targets)

    # phone_validation: if not yet verified (asked for phone), end the turn and wait
    # for next user message; if verified, continue normal routing
    def _after_phone_validation(state: AgentState) -> str:
        if not state.get("phone_verified"):
            return END
        return router(state)

    graph.add_conditional_edges(
        "phone_validation",
        _after_phone_validation,
        {**routing_targets, END: END},
    )

    # after all other nodes re-evaluate (except generate_response → END)
    for name in other_nodes:
        if name == "generate_response":
            graph.add_edge(name, END)
        else:
            graph.add_conditional_edges(name, router, routing_targets)

    return graph.compile()


agent = create_agent()
