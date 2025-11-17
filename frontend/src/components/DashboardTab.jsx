import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

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

  // Placeholder for fetching metrics
  const fetchMetrics = useCallback(async () => {
    // In a real application, this would fetch data from a new API endpoint
    // For now, we'll use dummy data or derive from logs if possible
    setMetrics(prev => ({
      ...prev,
      total_pnl: 1250.75,
      pnl_percentage: 12.5,
      win_rate: 65.2,
      active_strategies: 3,
      open_trades: 1,
      trend_signal: 'Uptrend',
    }));
  }, []);

  useEffect(() => {
    fetchBotStatus();
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000); // Refresh metrics every 5 seconds
    return () => clearInterval(interval);
  }, [fetchBotStatus, fetchMetrics]);

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

  const emergencyStop = () => {
    if (window.confirm('Are you sure you want to emergency stop the bot? This will attempt to close all open positions.')) {
      // Implement emergency stop logic here
      console.log('Emergency Stop initiated!');
      stopBot(); // For now, emergency stop just calls regular stop
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
        <div className="graph-placeholder">
          {/* Chart.js or Recharts will go here */}
          <p>Graph visualization coming soon...</p>
        </div>
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
              {/* Placeholder for recent trades */}
              <tr>
                <td>2025-11-18 10:30:00</td>
                <td>EURUSD</td>
                <td>Golden Cross</td>
                <td>CALL</td>
                <td>1.08500</td>
                <td>1.08550</td>
                <td className="text-success">+$5.00</td>
                <td>Closed (Win)</td>
              </tr>
              <tr>
                <td>2025-11-18 10:25:00</td>
                <td>GBPUSD</td>
                <td>RSI Dip</td>
                <td>PUT</td>
                <td>1.25000</td>
                <td>1.25020</td>
                <td className="text-danger">-$2.00</td>
                <td>Closed (Loss)</td>
              </tr>
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
