import asyncio
import json
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel

from agent import agent

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, list] = {}

# CallbackHandler reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from env
# (set in .mise.toml)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    sessions.setdefault(session_id, [])
    sessions[session_id].append({"role": "user", "content": req.message})

    langfuse_handler = CallbackHandler(trace_context={"trace_id": session_id})

    async def stream():
        from langchain_core.messages import HumanMessage

        result = agent.invoke(
            {
                "messages": [HumanMessage(content=m["content"]) for m in sessions[session_id] if m["role"] == "user"],
                "session_id": session_id,
            },
            config={"callbacks": [langfuse_handler]},
        )
        reply = result["messages"][-1].content
        sessions[session_id].append({"role": "assistant", "content": reply})

        for token in reply.split():
            yield f"data: {json.dumps({'type': 'token', 'content': token + ' '})}\n\n"
            await asyncio.sleep(0)

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/sessions/{session_id}/trace")
async def get_trace(session_id: str):
    return {"session_id": session_id, "messages": sessions.get(session_id, [])}
