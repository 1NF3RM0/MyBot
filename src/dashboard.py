import sys
import sqlite3
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QScrollArea
)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qt6agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# Function to load data from SQLite
def load_data():
    conn = sqlite3.connect('trading_log.db')
    df = pd.read_sql_query("SELECT * FROM trades", conn)
    conn.close()
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def load_confidence_data():
    conn = sqlite3.connect('trading_log.db')
    df_conf = pd.read_sql_query("SELECT * FROM strategy_confidence_log", conn)
    conn.close()
    if not df_conf.empty:
        df_conf['timestamp'] = pd.to_datetime(df_conf['timestamp'])
    return df_conf

class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trading Bot Performance Dashboard")
        self.setGeometry(100, 100, 1200, 800)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.df_trades = load_data()
        self.df_confidence = load_confidence_data()

        self.setup_ui()
        self.update_dashboard()

    def setup_ui(self):
        # Overall Performance
        self.performance_layout = QHBoxLayout()
        self.total_trades_label = QLabel("Total Trades: 0")
        self.total_wins_label = QLabel("Total Wins: 0")
        self.total_losses_label = QLabel("Total Losses: 0")
        self.win_rate_label = QLabel("Win Rate: 0.00%")
        self.performance_layout.addWidget(self.total_trades_label)
        self.performance_layout.addWidget(self.total_wins_label)
        self.performance_layout.addWidget(self.total_losses_label)
        self.performance_layout.addWidget(self.win_rate_label)
        self.main_layout.addLayout(self.performance_layout)

        # Strategy Performance
        self.main_layout.addWidget(QLabel("Strategy Performance:"))
        self.strategy_table = QTableWidget()
        self.strategy_table.setColumnCount(4)
        self.strategy_table.setHorizontalHeaderLabels(["Strategy", "Total Trades", "Wins", "Losses", "Win Rate (%)"])
        self.strategy_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.main_layout.addWidget(self.strategy_table)

        # Symbol Profitability
        self.main_layout.addWidget(QLabel("Symbol-Level Profitability:"))
        self.symbol_table = QTableWidget()
        self.symbol_table.setColumnCount(2)
        self.symbol_table.setHorizontalHeaderLabels(["Symbol", "Net Profit"])
        self.symbol_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.main_layout.addWidget(self.symbol_table)

        # Trade History
        self.main_layout.addWidget(QLabel("Trade History:"))
        self.trade_history_table = QTableWidget()
        self.trade_history_table.setColumnCount(len(self.df_trades.columns) if not self.df_trades.empty else 1)
        if not self.df_trades.empty:
            self.trade_history_table.setHorizontalHeaderLabels(self.df_trades.columns.tolist())
        self.trade_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.main_layout.addWidget(self.trade_history_table)

        # Confidence Score Evolution
        self.main_layout.addWidget(QLabel("Confidence Score Evolution:"))
        self.confidence_selector = QComboBox()
        self.confidence_selector.currentIndexChanged.connect(self.update_confidence_plot)
        self.main_layout.addWidget(self.confidence_selector)

        self.fig_confidence = Figure()
        self.ax_confidence = self.fig_confidence.add_subplot(111)
        self.canvas_confidence = FigureCanvas(self.fig_confidence)
        self.main_layout.addWidget(self.canvas_confidence)

    def update_dashboard(self):
        self.df_trades = load_data()
        self.df_confidence = load_confidence_data()

        if self.df_trades.empty:
            self.total_trades_label.setText("Total Trades: 0")
            self.total_wins_label.setText("Total Wins: 0")
            self.total_losses_label.setText("Total Losses: 0")
            self.win_rate_label.setText("Win Rate: 0.00%")
            self.strategy_table.setRowCount(0)
            self.symbol_table.setRowCount(0)
            self.trade_history_table.setRowCount(0)
            self.confidence_selector.clear()
            self.ax_confidence.clear()
            self.ax_confidence.text(0.5, 0.5, "No confidence data available", horizontalalignment='center', verticalalignment='center', transform=self.ax_confidence.transAxes)
            self.canvas_confidence.draw()
            return

        # Overall Performance
        total_trades = self.df_trades[self.df_trades['action'] == 'buy'].shape[0]
        total_wins = self.df_trades[self.df_trades['outcome'].str.contains('WON', na=False)].shape[0]
        total_losses = self.df_trades[self.df_trades['outcome'].str.contains('LOST', na=False)].shape[0]
        win_rate = (total_wins / total_trades) * 100 if total_trades > 0 else 0

        self.total_trades_label.setText(f"Total Trades: {total_trades}")
        self.total_wins_label.setText(f"Total Wins: {total_wins}")
        self.total_losses_label.setText(f"Total Losses: {total_losses}")
        self.win_rate_label.setText(f"Win Rate: {win_rate:.2f}%")

        # Strategy Performance
        strategy_performance = {}
        for strategy_name in self.df_trades['strategy'].unique():
            strategy_trades = self.df_trades[self.df_trades['strategy'] == strategy_name]
            
            strat_total_trades = strategy_trades[strategy_trades['action'] == 'buy'].shape[0]
            strat_wins = strategy_trades[strategy_trades['outcome'].str.contains('WON', na=False)].shape[0]
            strat_losses = strategy_trades[strategy_trades['outcome'].str.contains('LOST', na=False)].shape[0]
            strat_win_rate = (strat_wins / strat_total_trades) * 100 if strat_total_trades > 0 else 0
            
            strategy_performance[strategy_name] = {
                'Total Trades': strat_total_total_trades,
                'Wins': strat_wins,
                'Losses': strat_losses,
                'Win Rate (%)': strat_win_rate
            }
        
        self.strategy_table.setRowCount(len(strategy_performance))
        for i, (strategy, metrics) in enumerate(strategy_performance.items()):
            self.strategy_table.setItem(i, 0, QTableWidgetItem(strategy))
            self.strategy_table.setItem(i, 1, QTableWidgetItem(str(metrics['Total Trades'])))
            self.strategy_table.setItem(i, 2, QTableWidgetItem(str(metrics['Wins'])))
            self.strategy_table.setItem(i, 3, QTableWidgetItem(str(metrics['Losses'])))
            self.strategy_table.setItem(i, 4, QTableWidgetItem(f"{metrics['Win Rate (%)']:.2f}%"))

        # Symbol Profitability
        symbol_profitability = {}
        for symbol_name in self.df_trades['symbol'].unique():
            symbol_trades = self.df_trades[(self.df_trades['symbol'] == symbol_name) & (self.df_trades['action'].isin(['win', 'loss']))]
            
            total_profit = (symbol_trades[symbol_trades['action'] == 'win']['payout'].sum() -
                            symbol_trades[symbol_trades['action'] == 'win']['price'].sum())
            total_loss = (symbol_trades[symbol_trades['action'] == 'loss']['price'].sum() -
                          symbol_trades[symbol_trades['action'] == 'loss']['payout'].sum())
            
            net_profit = total_profit - total_loss
            
            symbol_profitability[symbol_name] = {
                'Net Profit': net_profit
            }
        
        self.symbol_table.setRowCount(len(symbol_profitability))
        for i, (symbol, metrics) in enumerate(symbol_profitability.items()):
            self.symbol_table.setItem(i, 0, QTableWidgetItem(symbol))
            self.symbol_table.setItem(i, 1, QTableWidgetItem(f"{metrics['Net Profit']:.2f}"))

        # Trade History
        self.trade_history_table.setRowCount(self.df_trades.shape[0])
        for row_idx, row_data in self.df_trades.sort_values('timestamp', ascending=False).iterrows():
            for col_idx, col_name in enumerate(self.df_trades.columns):
                self.trade_history_table.setItem(row_idx, col_idx, QTableWidgetItem(str(row_data[col_name])))

        # Confidence Score Evolution
        if not self.df_confidence.empty:
            self.confidence_selector.clear()
            self.confidence_selector.addItems(self.df_confidence['strategy_id'].unique().tolist())
            self.update_confidence_plot()
        else:
            self.confidence_selector.clear()
            self.ax_confidence.clear()
            self.ax_confidence.text(0.5, 0.5, "No confidence data available", horizontalalignment='center', verticalalignment='center', transform=self.ax_confidence.transAxes)
            self.canvas_confidence.draw()

    def update_confidence_plot(self):
        self.ax_confidence.clear()
        if not self.df_confidence.empty and self.confidence_selector.currentText():
            selected_strategy_for_confidence = self.confidence_selector.currentText()
            filtered_confidence_df = self.df_confidence[self.df_confidence['strategy_id'] == selected_strategy_for_confidence]
            
            self.ax_confidence.plot(filtered_confidence_df['timestamp'], filtered_confidence_df['confidence'], marker='o')
            self.ax_confidence.set_title(f'Confidence Score Evolution for {selected_strategy_for_confidence}')
            self.ax_confidence.set_xlabel('Time')
            self.ax_confidence.set_ylabel('Confidence Score')
            self.ax_confidence.tick_params(axis='x', rotation=45)
            self.fig_confidence.tight_layout()
        else:
            self.ax_confidence.text(0.5, 0.5, "No confidence data available", horizontalalignment='center', verticalalignment='center', transform=self.ax_confidence.transAxes)
        self.canvas_confidence.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dashboard = Dashboard()
    dashboard.show()
    sys.exit(app.exec())