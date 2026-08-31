from decimal import Decimal


def int_to_pretty(value) -> str:
    return f"{Decimal(value):,.2f}"
