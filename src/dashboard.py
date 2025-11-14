import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

st.set_page_config(layout="wide")

st.title("📈 Trading Bot Performance Dashboard")

# Function to load data from SQLite
@st.cache_data
def load_data():
    conn = sqlite3.connect('trading_log.db')
    df = pd.read_sql_query("SELECT * FROM trades", conn)
    conn.close()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

df = load_data()

if df.empty:
    st.warning("No trade data available to display. Run the bot to generate some data.")
else:
    st.header("📊 Overall Performance")

    total_trades = df[df['action'] == 'buy'].shape[0]
    total_wins = df[df['outcome'].str.contains('WON', na=False)].shape[0]
    total_losses = df[df['outcome'].str.contains('LOST', na=False)].shape[0]
    win_rate = (total_wins / total_trades) * 100 if total_trades > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Trades", total_trades)
    col2.metric("Total Wins", total_wins)
    col3.metric("Total Losses", total_losses)
    col4.metric("Win Rate", f"{win_rate:.2f}%")

    st.header("🚀 Strategy Performance")

    strategy_performance = {}
    for strategy_name in df['strategy'].unique():
        strategy_trades = df[df['strategy'] == strategy_name]
        
        strat_total_trades = strategy_trades[strategy_trades['action'] == 'buy'].shape[0]
        strat_wins = strategy_trades[strategy_trades['outcome'].str.contains('WON', na=False)].shape[0]
        strat_losses = strategy_trades[strategy_trades['outcome'].str.contains('LOST', na=False)].shape[0]
        strat_win_rate = (strat_wins / strat_total_trades) * 100 if strat_total_trades > 0 else 0
        
        strategy_performance[strategy_name] = {
            'Total Trades': strat_total_trades,
            'Wins': strat_wins,
            'Losses': strat_losses,
            'Win Rate (%)': strat_win_rate
        }
    
    st.dataframe(pd.DataFrame.from_dict(strategy_performance, orient='index').sort_values('Win Rate (%)', ascending=False))

    st.header("💰 Symbol-Level Profitability")

    symbol_profitability = {}
    for symbol_name in df['symbol'].unique():
        symbol_trades = df[(df['symbol'] == symbol_name) & (df['action'].isin(['win', 'loss']))]
        
        total_profit = symbol_trades[symbol_trades['action'] == 'win']['payout'].sum() - \
                       symbol_trades[symbol_trades['action'] == 'win']['price'].sum()
        total_loss = symbol_trades[symbol_trades['action'] == 'loss']['price'].sum() - \
                     symbol_trades[symbol_trades['action'] == 'loss']['payout'].sum()
        
        net_profit = total_profit - total_loss
        
        symbol_profitability[symbol_name] = {
            'Net Profit': net_profit
        }
    
    st.dataframe(pd.DataFrame.from_dict(symbol_profitability, orient='index').sort_values('Net Profit', ascending=False))

    st.header("📈 Trade History")
    st.dataframe(df.sort_values('timestamp', ascending=False))

    st.header("🧠 Confidence Score Evolution")

    @st.cache_data
    def load_confidence_data():
        conn = sqlite3.connect('trading_log.db')
        df_conf = pd.read_sql_query("SELECT * FROM strategy_confidence_log", conn)
        conn.close()
        df_conf['timestamp'] = pd.to_datetime(df_conf['timestamp'])
        return df_conf

    df_confidence = load_confidence_data()

    if df_confidence.empty:
        st.info("No confidence score data available yet. Run the bot for a while to see this graph populate.")
    else:
        selected_strategy_for_confidence = st.selectbox(
            "Select Strategy to View Confidence Evolution",
            df_confidence['strategy_id'].unique()
        )
        
        filtered_confidence_df = df_confidence[df_confidence['strategy_id'] == selected_strategy_for_confidence]
        
        fig_confidence = px.line(
            filtered_confidence_df,
            x='timestamp',
            y='confidence',
            title=f'Confidence Score Evolution for {selected_strategy_for_confidence}',
            labels={'timestamp': 'Time', 'confidence': 'Confidence Score'},
            markers=True
        )
        st.plotly_chart(fig_confidence, use_container_width=True)
