"""Run dataset items through the agent and score results in Langfuse v4."""
import json
import requests
from langfuse import Langfuse

lf = Langfuse(
    public_key="pk-lf-local-demo",
    secret_key="sk-lf-local-demo",
    host="http://localhost:3000",
)

BACKEND_URL = "http://localhost:8000"
DATASET_NAME = "refund-agent-evals"
RUN_NAME = "stub-agent-v0"

dataset = lf.get_dataset(DATASET_NAME)

for item in dataset.items:
    desc = item.metadata.get("description", item.id)
    print(f"\n→ {desc}")

    # Create span to wrap the agent call
    span = lf.start_observation(
        name=RUN_NAME,
        as_type="agent",
        input=item.input,
        metadata={"dataset_item_id": item.id, "dataset_name": DATASET_NAME, "description": desc},
    )

    try:
        response = requests.post(f"{BACKEND_URL}/chat", json=item.input, stream=True)
        tokens, session_id = [], None

        for line in response.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue
            event = json.loads(line[6:])
            if event["type"] == "token":
                tokens.append(event["content"])
            elif event["type"] == "done":
                session_id = event.get("session_id")

        reply = "".join(tokens).strip()
        expected = item.expected_output
        passed = expected.lower() in reply.lower()

        print(f"  expected '{expected}' in reply → {'PASS' if passed else 'FAIL'}")
        print(f"  reply: '{reply[:120]}'")

        span.update(output=reply, metadata={"session_id": session_id})
        span.end()

        span.score_trace(
            name="policy-compliance",
            value=1.0 if passed else 0.0,
            comment=f"Expected '{expected}' in response. Got: {reply[:200]}",
        )
    except Exception as e:
        span.update(metadata={"error": str(e)})
        span.end()
        raise

lf.flush()
print("\nDone. View results at http://localhost:3000")
