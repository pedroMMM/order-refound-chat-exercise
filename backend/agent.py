from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import operator


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    session_id: str


def stub_node(state: AgentState) -> AgentState:
    # TODO: implement — phone lookup, policy enforcement, tool calls
    return {"messages": [AIMessage(content="Agent not yet implemented.")], "session_id": state["session_id"]}


def create_agent():
    graph = StateGraph(AgentState)
    graph.add_node("respond", stub_node)
    graph.set_entry_point("respond")
    graph.add_edge("respond", END)
    return graph.compile()


agent = create_agent()
