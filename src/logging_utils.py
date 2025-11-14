import sqlite3

def init_db():
    """Initializes the SQLite database and creates the trades and strategy_confidence_log tables."""
    conn = sqlite3.connect('trading_log.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (timestamp TEXT, symbol TEXT, strategy TEXT, action TEXT, price REAL, payout REAL, outcome TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS strategy_confidence_log
                 (timestamp TEXT, strategy_id TEXT, confidence REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS strategy_performance
                 (strategy_id TEXT PRIMARY KEY, win_count INTEGER, loss_count INTEGER)''')
    conn.commit()
    conn.close()

def log_confidence_change(timestamp, strategy_id, confidence):
    """Logs a strategy's confidence score change to the SQLite database."""
    conn = sqlite3.connect('trading_log.db')
    c = conn.cursor()
    c.execute("INSERT INTO strategy_confidence_log VALUES (?,?,?)", (timestamp, strategy_id, confidence))
    conn.commit()
    conn.close()

def log_trade(timestamp, symbol, strategy, action, price, payout, outcome):
    """Logs a trade to the SQLite database."""
    conn = sqlite3.connect('trading_log.db')
    c = conn.cursor()
    c.execute("INSERT INTO trades VALUES (?,?,?,?,?,?,?)", (timestamp, symbol, strategy, action, price, payout, outcome))
    conn.commit()
    conn.close()

def update_strategy_performance(strategy_id, outcome):
    """Updates the win/loss count for a strategy in the strategy_performance table."""
    conn = sqlite3.connect('trading_log.db')
    c = conn.cursor()
    c.execute("SELECT win_count, loss_count FROM strategy_performance WHERE strategy_id = ?", (strategy_id,))
    row = c.fetchone()
    if row:
        win_count, loss_count = row
        if outcome == 'win':
            win_count += 1
        else:
            loss_count += 1
        c.execute("UPDATE strategy_performance SET win_count = ?, loss_count = ? WHERE strategy_id = ?", (win_count, loss_count, strategy_id))
    else:
        if outcome == 'win':
            c.execute("INSERT INTO strategy_performance (strategy_id, win_count, loss_count) VALUES (?, 1, 0)", (strategy_id,))
        else:
            c.execute("INSERT INTO strategy_performance (strategy_id, win_count, loss_count) VALUES (?, 0, 1)", (strategy_id,))
    conn.commit()
    conn.close()
