import sqlite3
import pandas as pd

def generate_strategy_report():
    """Generates a report on strategy performance."""
    conn = sqlite3.connect('trading_log.db')
    df = pd.read_sql_query("SELECT * FROM trades", conn)
    conn.close()

    if df.empty:
        print("No trade data available to generate a report.")
        return

    # Filter for 'buy' actions to analyze executed trades
    executed_trades = df[df['action'] == 'buy']

    if executed_trades.empty:
        print("No executed trades to analyze.")
        return

    strategy_performance = {}

    for strategy_name in executed_trades['strategy'].unique():
        strategy_trades = executed_trades[executed_trades['strategy'] == strategy_name]
        
        total_trades = len(strategy_trades)
        if total_trades == 0:
            continue

        # Assuming a 'win' if payout > price (simplified, actual profit calculation might be more complex)
        # And 'outcome' field might need to be parsed for more detailed win/loss
        # For now, let's use a simplified approach based on payout vs buy_price
        wins = strategy_trades[strategy_trades['payout'] > strategy_trades['price']].shape[0]
        losses = total_trades - wins
        win_ratio = (wins / total_trades) * 100 if total_trades > 0 else 0
        average_payout = strategy_trades['payout'].mean()
        average_price = strategy_trades['price'].mean()

        strategy_performance[strategy_name] = {
            'Total Trades': total_trades,
            'Wins': wins,
            'Losses': losses,
            'Win Ratio (%)': f"{win_ratio:.2f}%",
            'Average Payout': f"{average_payout:.2f}",
            'Average Buy Price': f"{average_price:.2f}"
        }

    print("\n--- Strategy Performance Report ---")
    for strategy, metrics in strategy_performance.items():
        print(f"\nStrategy: {strategy}")
        for metric, value in metrics.items():
            print(f"  {metric}: {value}")

if __name__ == "__main__":
    generate_strategy_report()
