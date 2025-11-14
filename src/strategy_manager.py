import sqlite3
import pandas as pd
import random
import datetime
from src import logging_utils

class Strategy:
    def __init__(self, name, func, params, confidence=1.0, is_active=True):
        self.name = name
        self.func = func
        self.params = params # Dictionary of tunable parameters
        self.confidence = confidence
        self.is_active = is_active
        self.id = f"{name}_{hash(frozenset(params.items()))}" # Unique ID for variant

    def __str__(self):
        return f"Strategy(Name: {self.name}, Confidence: {self.confidence:.2f}, Active: {self.is_active}, Params: {self.params})"

    def __repr__(self):
        return self.__str__()

def get_strategy_performance():
    """Retrieves and calculates performance metrics for each strategy from the strategy_performance table.

    Returns:
        dict: A dictionary where keys are strategy_ids and values are dictionaries
              containing 'total_trades', 'wins', 'losses', 'win_rate'.
    """
    conn = sqlite3.connect('trading_log.db')
    df = pd.read_sql_query("SELECT * FROM strategy_performance", conn)
    conn.close()

    performance = {}
    if df.empty:
        return performance

    for index, row in df.iterrows():
        strategy_id = row['strategy_id']
        wins = row['win_count']
        losses = row['loss_count']
        total_trades = wins + losses
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0

        performance[strategy_id] = {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate
        }
    return performance

def adjust_strategy_confidence(strategies, performance, min_trades=0, win_rate_threshold=0): # Temporarily set to 0 for testing
    """Adjusts strategy confidence scores based on recent performance.

    Args:
        strategies (dict): A dictionary of Strategy objects.
        performance (dict): Performance metrics from get_strategy_performance.
        min_trades (int): Minimum number of trades required to consider a strategy for adjustment.
        win_rate_threshold (int): Win rate percentage below which a strategy might be disabled.

    Returns:
        dict: Updated Strategy objects.
    """
    for strategy_id, strategy_obj in strategies.items():
        strategy_name = strategy_obj.name
        metrics = performance.get(strategy_id) # Use strategy_id for performance lookup

        if metrics and metrics['total_trades'] >= min_trades:
            if metrics['win_rate'] < win_rate_threshold:
                # Check for recovery mode
                if not strategy_obj.is_active: # If currently disabled
                    conn = sqlite3.connect('trading_log.db')
                    df = pd.read_sql_query(f"SELECT outcome FROM trades WHERE strategy = '{strategy_id}' AND action IN ('win', 'loss') ORDER BY timestamp DESC LIMIT 3", conn)
                    conn.close()
                    
                    if len(df) == 3 and all('WON' in outcome for outcome in df['outcome'].values):
                        print(f"Strategy {strategy_name} (ID: {strategy_id}) re-enabled due to 3 consecutive wins in recovery mode.")
                        strategy_obj.is_active = True
                        strategy_obj.confidence = 0.5 # Re-enable with a base confidence
                        logging_utils.log_confidence_change(datetime.datetime.now(), strategy_id, strategy_obj.confidence)
                    else:
                        print(f"Strategy {strategy_name} (ID: {strategy_id}) disabled due to low win rate ({metrics['win_rate']:.2f}%).")
                        strategy_obj.is_active = False
                        strategy_obj.confidence = 0  # Effectively disable
                else:
                    print(f"Strategy {strategy_name} (ID: {strategy_id}) disabled due to low win rate ({metrics['win_rate']:.2f}%).")
                    strategy_obj.is_active = False
                    strategy_obj.confidence = 0  # Effectively disable
                    logging_utils.log_confidence_change(datetime.datetime.now(), strategy_id, strategy_obj.confidence)
            else:
                # Adjust confidence based on win rate (simple linear scaling)
                new_confidence = 0.5 + (metrics['win_rate'] / 100) * 0.5  # Scale from 0.5 to 1.0
                strategy_obj.confidence = max(0.1, min(1.0, new_confidence)) # Keep within 0.1 and 1.0
                strategy_obj.is_active = True # Ensure it's active if performing well
                print(f"Strategy {strategy_name} (ID: {strategy_id}) confidence adjusted to {strategy_obj.confidence:.2f} (Win Rate: {metrics['win_rate']:.2f}%).")
                logging_utils.log_confidence_change(datetime.datetime.now(), strategy_id, strategy_obj.confidence)
        elif strategy_obj.is_active: # If not enough trades, but currently active, keep it active
            print(f"Strategy '{strategy_name}' (ID: {strategy_id}) has fewer than {min_trades} trades ({metrics['total_trades'] if metrics else 0}). Skipping confidence adjustment for now.")
        elif not strategy_obj.is_active: # If not enough trades and already inactive, keep it inactive
            print(f"Strategy '{strategy_name}' (ID: {strategy_id}) is inactive and has fewer than {min_trades} trades ({metrics['total_trades'] if metrics else 0}). Keeping inactive.")

    return strategies

if __name__ == "__main__":
    # Example Usage:
    # Assuming initial confidence scores for strategies
    initial_confidence = {
        'evaluate_golden_cross': 1.0,
        'evaluate_rsi_dip': 0.8,
        'evaluate_macd_crossover': 0.9,
        'evaluate_bollinger_breakout': 0.85
    }

    performance_data = get_strategy_performance()
    updated_conf, disabled_strat = adjust_strategy_confidence(initial_confidence, performance_data)

    print("\n--- Strategy Performance Summary ---")
    for strategy, metrics in performance_data.items():
        print(f"Strategy: {strategy}")
        for metric, value in metrics.items():
            print(f"  {metric}: {value}")

    print("\n--- Adjusted Confidence Scores ---")
    for strategy, confidence in updated_conf.items():
        print(f"  {strategy}: {confidence:.2f}")

    if disabled_strat:
        print("\n--- Disabled Strategies ---")
        for strategy in disabled_strat:
            print(f"  {strategy}")
