from decimal import Decimal

from django.conf import settings


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    input_price, output_price = settings.AI_PRICES.get(model, (0.0, 0.0))
    cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
    return Decimal(str(round(cost, 6)))
