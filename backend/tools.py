"""Agent tools — read from data/ JSON files."""
import json
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def _load(filename: str) -> list[dict]:
    with open(DATA_DIR / filename) as f:
        return json.load(f)


def lookup_customer_by_phone(phone: str) -> dict:
    """Resolve customer_id from phone number. Demo mode always succeeds."""
    digits = "".join(c for c in phone if c.isdigit())
    customers = _load("customers.json")
    for c in customers:
        if "".join(d for d in c["phone"] if d.isdigit()) == digits:
            return {
                "customer_id": c["customer_id"],
                "name": c["name"],
                "note": "bypassing phone verification (demo mode)",
            }
    first = customers[0]
    return {
        "customer_id": first["customer_id"],
        "name": first["name"],
        "note": f"phone not found — defaulting to {first['customer_id']} (demo mode)",
    }


def get_customer(customer_id: str) -> dict:
    """Fetch customer profile and order history."""
    customers = _load("customers.json")
    for c in customers:
        if c["customer_id"] == customer_id:
            return c
    return {"error": f"Customer {customer_id} not found"}


def get_order(order_id: str) -> dict:
    """Fetch order details."""
    orders = _load("orders.json")
    for o in orders:
        if o["order_id"] == order_id:
            return o
    return {"error": f"Order {order_id} not found"}


def check_refund_eligibility(order_id: str) -> dict:
    """
    Run policy rules against an order.
    Returns: {decision: eligible|denied|escalate, reason: str}
    """
    orders = _load("orders.json")
    order = next((o for o in orders if o["order_id"] == order_id), None)
    if not order:
        return {"decision": "denied", "reason": f"Order {order_id} not found"}

    if order["status"] == "refunded":
        return {"decision": "denied", "reason": "This order has already been refunded"}

    if order["is_final_sale"]:
        return {"decision": "denied", "reason": "Final sale items are not refundable"}

    order_date = date.fromisoformat(order["date"])
    age_days = (date.today() - order_date).days

    if order.get("is_defective"):
        return {
            "decision": "eligible",
            "reason": "Item is defective/damaged — eligible regardless of age. Photo evidence may be requested.",
        }

    if age_days > 30:
        return {
            "decision": "denied",
            "reason": f"Order is {age_days} days old. Refunds must be requested within 30 days of purchase",
        }

    if order["price"] > 500:
        return {
            "decision": "escalate",
            "reason": f"Order total ${order['price']:.2f} exceeds $500 — must be escalated to human agent",
        }

    customer_id = order["customer_id"]
    customers = _load("customers.json")
    customer = next((c for c in customers if c["customer_id"] == customer_id), None)
    if customer:
        cutoff = date(date.today().year - (1 if date.today().month <= 6 else 0),
                      (date.today().month + 6 - 1) % 12 + 1,
                      date.today().day)
        recent_refunds = sum(
            1 for o in orders
            if o["customer_id"] == customer_id
            and o["status"] == "refunded"
            and date.fromisoformat(o["date"]) >= cutoff
        )
        if recent_refunds >= 2:
            return {
                "decision": "denied",
                "reason": "Customer has reached the 2-refund limit for the past 6 months",
            }

    return {"decision": "eligible", "reason": "Order meets all refund criteria"}


def process_refund(order_id: str) -> dict:
    """Mark order as refunded. Call only after eligibility confirmed."""
    orders = _load("orders.json")
    for o in orders:
        if o["order_id"] == order_id:
            if o["status"] == "refunded":
                return {"success": False, "message": "Order already refunded"}
            o["status"] = "refunded"
            with open(DATA_DIR / "orders.json", "w") as f:
                json.dump(orders, f, indent=2)
            return {"success": True, "message": f"Refund processed for {order_id}"}
    return {"success": False, "message": f"Order {order_id} not found"}


def escalate_to_human(order_id: str, reason: str) -> dict:
    """Flag order for human review."""
    return {
        "success": True,
        "order_id": order_id,
        "reason": reason,
        "message": "Escalated to human agent",
    }
