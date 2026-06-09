import json
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langfuse.langchain import CallbackHandler
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel

from agent import agent

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, dict] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@app.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    prev = sessions.get(session_id, {
        "messages": [],
        "session_id": session_id,
        "customer_id": None,
        "phone_verified": False,
        "phone_number": None,
    })

    state_in = {
        **prev,
        "messages": prev["messages"] + [HumanMessage(content=req.message)],
    }

    trace_id = session_id.replace("-", "")
    langfuse_handler = CallbackHandler(trace_context={"trace_id": trace_id})

    async def stream():
        final_state = dict(prev)

        for stream_mode, data in agent.stream(
            state_in,
            config={"callbacks": [langfuse_handler]},
            stream_mode=["updates", "custom"],
        ):
            if stream_mode == "custom":
                # nodes own event creation — just forward
                yield _sse(data)

            elif stream_mode == "updates":
                # merge state for session persistence
                for node_name, state_update in data.items():
                    for k, v in state_update.items():
                        if k != "messages":
                            final_state[k] = v
                    if "messages" in state_update:
                        final_state["messages"] = state_update["messages"]

        # persist session
        sessions[session_id] = {
            "messages": final_state.get("messages", []),
            "session_id": session_id,
            "customer_id": final_state.get("customer_id"),
            "phone_verified": final_state.get("phone_verified", False),
            "phone_number": final_state.get("phone_number"),
        }

        # emit session state snapshot
        yield _sse({"type": "session_state", "data": {
            "customer_id": sessions[session_id]["customer_id"],
            "phone_verified": sessions[session_id]["phone_verified"],
            "phone_number": sessions[session_id]["phone_number"],
        }})

        # stream final reply tokens
        reply = ""
        for msg in reversed(sessions[session_id]["messages"]):
            if isinstance(msg, AIMessage) and not msg.tool_calls and msg.content:
                reply = msg.content
                break
        for token in reply.split():
            yield _sse({"type": "token", "content": token + " "})

        yield _sse({"type": "done", "session_id": session_id})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/sessions/{session_id}/trace")
async def get_trace(session_id: str):
    s = sessions.get(session_id)
    if not s:
        return {"session_id": session_id, "messages": []}
    msgs = [{"type": type(m).__name__, "content": m.content} for m in s["messages"]]
    return {"session_id": session_id, "messages": msgs, "customer_id": s.get("customer_id")}
