import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const DashboardTab = ({ logs }) => {
  const { token } = useAuth();
  const [botStatus, setBotStatus] = useState('stopped');
  const [metrics, setMetrics] = useState({
    total_pnl: 0,
    pnl_percentage: 0,
    win_rate: 0,
    active_strategies: 0,
    open_trades: 0,
    trend_signal: 'N/A',
  });
  const [performanceData, setPerformanceData] = useState([]);
  const [recentTrades, setRecentTrades] = useState([]);
  const [account, setAccount] = useState({ balance: null, currency: null });

  const fetchBotStatus = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8000/bot/status', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setBotStatus(data.status);
      }
    } catch (error) {
      console.error('Error fetching bot status:', error);
    }
  }, [token]);

  const fetchMetrics = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8000/bot/metrics', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setMetrics(data);
      }
    } catch (error) {
      console.error('Error fetching metrics:', error);
    }
  }, [token]);

  const fetchRecentTrades = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8000/tradelog/recent', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setRecentTrades(data);
      }
    } catch (error) {
      console.error('Error fetching recent trades:', error);
    }
  }, [token]);

  const fetchPerformanceData = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8000/bot/performance', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setPerformanceData(data);
      }
    } catch (error) {
      console.error('Error fetching performance data:', error);
    }
  }, [token]);

  const fetchAccountInfo = useCallback(async () => {
    if (!token) return;
    try {
        const response = await fetch('http://localhost:8000/bot/account', {
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (response.ok) {
            const data = await response.json();
            setAccount(data);
        }
    } catch (error) {
        console.error('Failed to fetch account info:', error);
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      fetchBotStatus();
      fetchMetrics();
      fetchRecentTrades();
      fetchPerformanceData();
      fetchAccountInfo();
      const interval = setInterval(() => {
        fetchMetrics();
        fetchRecentTrades();
        fetchPerformanceData();
        fetchAccountInfo();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [token, fetchBotStatus, fetchMetrics, fetchRecentTrades, fetchPerformanceData, fetchAccountInfo]);

  const startBot = async () => {
    try {
      const response = await fetch('http://localhost:8000/bot/start', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        setBotStatus('running');
      } else {
        const errorData = await response.json();
        console.error('Error starting bot:', errorData.message);
      }
    } catch (error) {
      console.error('Network error starting bot:', error);
    }
  };

  const stopBot = async () => {
    try {
      const response = await fetch('http://localhost:8000/bot/stop', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        setBotStatus('stopped');
      } else {
        const errorData = await response.json();
        console.error('Error stopping bot:', errorData.message);
      }
    } catch (error) {
      console.error('Network error stopping bot:', error);
    }
  };

  const emergencyStop = async () => {
    if (window.confirm('Are you sure you want to emergency stop the bot? This will attempt to close all open positions.')) {
      try {
        const response = await fetch('http://localhost:8000/bot/emergency_stop', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (response.ok) {
          setBotStatus('stopped');
        } else {
          const errorData = await response.json();
          console.error('Error during emergency stop:', errorData.message);
        }
      } catch (error) {
        console.error('Network error during emergency stop:', error);
      }
    }
  };

  return (
    <div className="dashboard-tab">
      <div className="dashboard-header">
        <h2>Dashboard Overview</h2>
        <div className="bot-controls">
          <button onClick={startBot} disabled={botStatus === 'running'} className="btn-success">Start Bot</button>
          <button onClick={stopBot} disabled={botStatus === 'stopped'} className="btn-warning">Stop Bot</button>
          <button onClick={emergencyStop} className="btn-danger">Emergency Stop</button>
          <span className={`status-indicator ${botStatus}`}>Status: {botStatus.toUpperCase()}</span>
        </div>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <h3>Account Balance</h3>
          <p>{account.balance ? `${account.balance.toFixed(2)} ${account.currency}` : 'N/A'}</p>
        </div>
        <div className="metric-card">
          <h3>Total P/L</h3>
          <p className={metrics.total_pnl >= 0 ? 'text-success' : 'text-danger'}>${metrics.total_pnl.toFixed(2)}</p>
          <span className={metrics.pnl_percentage >= 0 ? 'text-success' : 'text-danger'}>{metrics.pnl_percentage.toFixed(2)}%</span>
        </div>
        <div className="metric-card">
          <h3>Win Rate</h3>
          <p>{metrics.win_rate.toFixed(2)}%</p>
          <span>Trend Signal: {metrics.trend_signal}</span>
        </div>
        <div className="metric-card">
          <h3>Active Strategies</h3>
          <p>{metrics.active_strategies}</p>
        </div>
        <div className="metric-card">
          <h3>Open Trades</h3>
          <p>{metrics.open_trades}</p>
        </div>
      </div>

      <div className="performance-graph">
        <h3>Performance Graph (P/L Over Time)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart
            data={performanceData}
            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
            <XAxis dataKey="timestamp" stroke="var(--text-muted)" />
            <YAxis stroke="var(--text-muted)" />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--secondary-bg)',
                borderColor: 'var(--border-color)',
              }}
            />
            <Legend />
            <Line type="monotone" dataKey="pnl" name="Cumulative P/L" stroke="var(--accent-color)" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="recent-trades">
        <h3>Recent Trades</h3>
        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Symbol</th>
                <th>Strategy</th>
                <th>Type</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>P/L</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {recentTrades.length > 0 ? (
                recentTrades.map(trade => (
                  <tr key={trade.id}>
                    <td>{new Date(trade.timestamp).toLocaleString()}</td>
                    <td>{trade.symbol}</td>
                    <td>{trade.strategy}</td>
                    <td>{trade.type}</td>
                    <td>{trade.entry_price ? trade.entry_price.toFixed(5) : 'N/A'}</td>
                    <td>{trade.exit_price ? trade.exit_price.toFixed(5) : 'N/A'}</td>
                    <td className={trade.pnl >= 0 ? 'text-success' : 'text-danger'}>{trade.pnl ? `$${trade.pnl.toFixed(2)}` : 'N/A'}</td>
                    <td>{trade.status}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center' }}>No recent trades found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="live-logs">
        <h3>Live Logs</h3>
        <div className="log-container">
          {logs.map((log, index) => (
            <div key={index} className="log-message">{log}</div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DashboardTab;
