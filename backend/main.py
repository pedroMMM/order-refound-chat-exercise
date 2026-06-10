import json
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langfuse.langchain import CallbackHandler
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk
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
    prev = sessions.get(
        session_id,
        {
            "messages": [],
            "session_id": session_id,
            "customer_id": None,
            "phone_verified": False,
            "phone_number": None,
            "customer_profile": None,
        },
    )

    state_in = {
        **prev,
        "messages": prev["messages"] + [HumanMessage(content=req.message)],
        # reset per-turn fields
        "order_id": None,
        "intent": None,
        "eligibility": None,
        "action_taken": None,
    }

    trace_id = session_id.replace("-", "")
    langfuse_handler = CallbackHandler(trace_context={"trace_id": trace_id})

    async def stream():
        partial_state: dict = {}
        all_messages: list = list(state_in["messages"])

        config = {"callbacks": [langfuse_handler]}

        try:
            async for stream_mode, data in agent.astream(
                state_in,
                config=config,
                stream_mode=["updates", "custom", "messages"],
            ):
                if stream_mode == "custom":
                    yield _sse(data)

                elif stream_mode == "messages":
                    msg_chunk, msg_meta = data
                    if (
                        isinstance(msg_chunk, AIMessageChunk)
                        and msg_meta.get("langgraph_node") == "generate_response"
                        and isinstance(msg_chunk.content, str)
                        and msg_chunk.content
                    ):
                        yield _sse({"type": "token", "content": msg_chunk.content})

                elif stream_mode == "updates":
                    for _node, state_update in data.items():
                        if not isinstance(state_update, dict):
                            continue
                        for k, v in state_update.items():
                            if k != "messages":
                                partial_state[k] = v
                        if "messages" in state_update:
                            all_messages.extend(state_update["messages"])

        except Exception as exc:
            yield _sse({"type": "error", "message": str(exc)})

        # Persist session
        sessions[session_id] = {
            "messages": all_messages,
            "session_id": session_id,
            "customer_id": partial_state.get("customer_id", prev.get("customer_id")),
            "phone_verified": partial_state.get("phone_verified", prev.get("phone_verified", False)),
            "phone_number": partial_state.get("phone_number", prev.get("phone_number")),
            "customer_profile": partial_state.get("customer_profile", prev.get("customer_profile")),
        }

        yield _sse({
            "type": "session_state",
            "data": {
                "customer_id": sessions[session_id]["customer_id"],
                "phone_verified": sessions[session_id]["phone_verified"],
                "phone_number": sessions[session_id]["phone_number"],
            },
        })
        yield _sse({"type": "done", "session_id": session_id})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/sessions/{session_id}/trace")
async def get_trace(session_id: str):
    s = sessions.get(session_id)
    if not s:
        return {"session_id": session_id, "messages": []}
    msgs = [{"type": type(m).__name__, "content": m.content} for m in s["messages"]]
    return {
        "session_id": session_id,
        "messages": msgs,
        "customer_id": s.get("customer_id"),
    }
