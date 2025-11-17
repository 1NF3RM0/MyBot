import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

const StrategiesTab = () => {
  const { token } = useAuth();
  const [strategies, setStrategies] = useState([]);

  const fetchStrategies = useCallback(async () => {
    // This endpoint needs to be created in the backend
    // It should return a list of strategies with their status and performance metrics
    // For now, using dummy data
    const dummyStrategies = [
      { id: 'golden_cross', name: 'Golden Cross', is_active: true, win_rate: 60, total_trades: 120, pnl: 1500 },
      { id: 'rsi_dip', name: 'RSI Dip', is_active: false, win_rate: 55, total_trades: 80, pnl: 750 },
      { id: 'macd_crossover', name: 'MACD Crossover', is_active: true, win_rate: 62, total_trades: 150, pnl: 2100 },
      { id: 'bollinger_breakout', name: 'Bollinger Breakout', is_active: false, win_rate: 50, total_trades: 60, pnl: -100 },
      { id: 'awesome_oscillator', name: 'Awesome Oscillator', is_active: true, win_rate: 58, total_trades: 90, pnl: 900 },
      { id: 'ml_prediction', name: 'ML Prediction', is_active: true, win_rate: 68, total_trades: 200, pnl: 3500 },
    ];
    setStrategies(dummyStrategies);
  }, []);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  const toggleStrategy = async (strategyId) => {
    // This endpoint needs to be created in the backend
    // It should update the strategy's active status for the current user
    console.log(`Toggling strategy: ${strategyId}`);
    setStrategies(prevStrategies =>
      prevStrategies.map(s =>
        s.id === strategyId ? { ...s, is_active: !s.is_active } : s
      )
    );
  };

  const addNewStrategy = () => {
    alert('Adding new strategies is a complex feature and requires backend implementation. This is a placeholder.');
    // This would involve a form to define a new strategy,
    // which would then need to be saved to the backend and integrated into the bot.
  };

  return (
    <div className="strategies-tab">
      <div className="tab-header">
        <h2>Strategy Management</h2>
        <button onClick={addNewStrategy} className="btn-primary">Add New Strategy</button>
      </div>

      <div className="strategies-grid">
        {strategies.map((strategy) => (
          <div key={strategy.id} className="strategy-card">
            <h3>{strategy.name}</h3>
            <p>Status: <span className={strategy.is_active ? 'text-success' : 'text-danger'}>{strategy.is_active ? 'Active' : 'Inactive'}</span></p>
            <p>Win Rate: {strategy.win_rate}%</p>
            <p>Total Trades: {strategy.total_trades}</p>
            <p>P/L: <span className={strategy.pnl >= 0 ? 'text-success' : 'text-danger'}>${strategy.pnl.toFixed(2)}</span></p>
            <button onClick={() => toggleStrategy(strategy.id)} className={strategy.is_active ? 'btn-warning' : 'btn-success'}>
              {strategy.is_active ? 'Disable' : 'Enable'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StrategiesTab;
