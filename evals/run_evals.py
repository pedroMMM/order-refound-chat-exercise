"""Run dataset experiments via Langfuse SDK (v4 experiments API)."""
import json
import requests
from langfuse import get_client, Evaluation

BACKEND_URL = "http://localhost:8000"
DATASET_NAME = "refund-agent-evals"
RUN_NAME = "stub-agent-v0"

lf = get_client()


def call_agent(message: str) -> tuple[str, str | None]:
    """Call /chat endpoint, collect SSE stream. Returns (reply, session_id)."""
    response = requests.post(
        f"{BACKEND_URL}/chat",
        json={"message": message},
        stream=True,
    )
    tokens, session_id = [], None
    for line in response.iter_lines():
        if not line or not line.startswith(b"data: "):
            continue
        event = json.loads(line[6:])
        if event["type"] == "token":
            tokens.append(event["content"])
        elif event["type"] == "done":
            session_id = event.get("session_id")
    return "".join(tokens).strip(), session_id


def task(*, item, **kwargs) -> str:
    """Task function called per dataset item."""
    reply, _ = call_agent(item.input["message"])
    return reply


def policy_compliance(*, input, output, expected_output, **kwargs) -> Evaluation:
    """Score: 1.0 if expected keyword present in reply, else 0.0."""
    passed = expected_output and expected_output.lower() in output.lower()
    return Evaluation(
        name="policy-compliance",
        value=1.0 if passed else 0.0,
        comment=f"Expected '{expected_output}' in reply. Got: '{output[:200]}'",
    )


dataset = lf.get_dataset(DATASET_NAME)

result = dataset.run_experiment(
    name=RUN_NAME,
    description="Empty LangGraph stub — all evals expected to fail",
    task=task,
    evaluators=[policy_compliance],
    metadata={"backend": BACKEND_URL, "agent": "stub"},
)

print(result.format())
print(f"\nView results at http://localhost:3000")
