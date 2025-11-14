import random

def calculate_lot_size(balance, risk_percentage):
    """Calculates the lot size for a trade."""
    risk_amount = balance * risk_percentage
    num_lots = 1
    amount_per_lot = risk_amount / num_lots

    # Ensure amount per lot is within limits
    min_stake = 0.50
    max_payout_factor = 10.0  # Assuming a max payout of 100 for a stake of 10

    if amount_per_lot < min_stake:
        amount_per_lot = min_stake
    elif amount_per_lot * max_payout_factor > 100:
        amount_per_lot = 100 / max_payout_factor

    return num_lots, amount_per_lot