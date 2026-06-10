"""Run dataset experiments via Langfuse SDK (v4 experiments API).

Usage: mise run eval-run
"""

import json
import requests
from langfuse import get_client, Evaluation

BACKEND_URL = "http://localhost:8000"
DATASET_NAME = "refund-agent-evals-v2"
RUN_NAME = "policy-enforcement-v1"

lf = get_client()


def _send(message: str, session_id: str | None) -> tuple[str, str | None]:
    """Send one message, collect SSE stream. Returns (reply, session_id)."""
    response = requests.post(
        f"{BACKEND_URL}/chat",
        json={"message": message, "session_id": session_id},
        stream=True,
    )
    tokens: list[str] = []
    out_session_id = session_id
    for line in response.iter_lines():
        if not line or not line.startswith(b"data: "):
            continue
        event = json.loads(line[6:])
        if event["type"] == "token":
            tokens.append(event["content"])
        elif event["type"] == "done":
            out_session_id = event.get("session_id", session_id)
    return "".join(tokens).strip(), out_session_id


def call_agent(phone: str, messages: list[str]) -> str:
    """Multi-turn conversation: send phone first, then each message in order."""
    session_id: str | None = None

    # Phone verification turn
    _, session_id = _send(phone, session_id)

    # Subsequent message turns — return final reply
    reply = ""
    for msg in messages:
        reply, session_id = _send(msg, session_id)

    return reply


def task(*, item, **kwargs) -> str:
    """Task function called per dataset item."""
    phone = item.input["phone"]
    messages = item.input["messages"]
    return call_agent(phone, messages)


def policy_compliance(*, input, output, expected_output, **kwargs) -> Evaluation:
    """Score: 1.0 if expected keyword present in reply (case-insensitive), else 0.0."""
    passed = bool(expected_output) and expected_output.lower() in output.lower()
    return Evaluation(
        name="policy-compliance",
        value=1.0 if passed else 0.0,
        comment=f"Expected '{expected_output}' in reply. Got: '{output[:300]}'",
    )


dataset = lf.get_dataset(DATASET_NAME)

result = dataset.run_experiment(
    name=RUN_NAME,
    description="Full policy enforcement: eligible, final-sale, escalation, age, pressure, injection.",
    task=task,
    evaluators=[policy_compliance],
    metadata={"backend": BACKEND_URL},
)

print(result.format())
print(f"\nView results at http://localhost:3000")
