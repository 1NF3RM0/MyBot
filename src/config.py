APP_ID = '110743'  # Replace with your Deriv App ID
API_TOKEN = 'D8oDxj9TEYZLcKG'  # Replace with your Deriv API Token

# Stop-loss and take-profit parameters
STOP_LOSS_PERCENT = 5  # Sell if loss exceeds 5% of buy price
TAKE_PROFIT_PERCENT = 10 # Sell if profit exceeds 10% of buy price

# Proposal validation parameters
# These parameters define the criteria for accepting a trade proposal.
# Adjust them to control the bot's aggressiveness in entering trades.
MAX_ASK_PRICE = 1  # Maximum acceptable ask price for a contract
MIN_PAYOUT = 1     # Minimum acceptable payout for a contract
MIN_COMBINED_CONFIDENCE = 1.5 # Example threshold, can be tuned

LOOP_DELAY = 60 # Delay between trading cycles in seconds
