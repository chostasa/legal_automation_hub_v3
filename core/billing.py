import stripe
from core.error_handling import handle_error
from core.auth import get_tenant_id

STRIPE_API_KEY = "sk_test_placeholder"

stripe.api_key = STRIPE_API_KEY

def create_customer(email: str, tenant_id: str = None):
    try:
        tenant_id = tenant_id or get_tenant_id()
        return stripe.Customer.create(email=email, metadata={"tenant_id": tenant_id})
    except Exception as e:
        handle_error(e, code="BILLING_CREATE_CUSTOMER")
        return None

def create_subscription(customer_id: str, price_id: str):
    try:
        return stripe.Subscription.create(customer=customer_id, items=[{"price": price_id}])
    except Exception as e:
        handle_error(e, code="BILLING_CREATE_SUBSCRIPTION")
        return None

def fetch_invoices(customer_id: str):
    try:
        return stripe.Invoice.list(customer=customer_id)
    except Exception as e:
        handle_error(e, code="BILLING_FETCH_INVOICES")
        return []

def record_usage(subscription_item_id: str, quantity: int):
    try:
        return stripe.UsageRecord.create(
            subscription_item=subscription_item_id,
            quantity=quantity,
            timestamp=int(__import__('time').time()),
            action="increment"
        )
    except Exception as e:
        handle_error(e, code="BILLING_RECORD_USAGE")
        return None

def cancel_subscription(subscription_id: str):
    try:
        return stripe.Subscription.delete(subscription_id)
    except Exception as e:
        handle_error(e, code="BILLING_CANCEL_SUBSCRIPTION")
        return None