import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

const StrategiesTab = () => {
  const { token } = useAuth();
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchStrategies = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/strategies', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setStrategies(data);
      } else {
        console.error('Failed to fetch strategies');
      }
    } catch (error) {
      console.error('Network error fetching strategies:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  const toggleStrategy = async (strategyId) => {
    try {
      const response = await fetch(`http://localhost:8000/strategies/${strategyId}/toggle`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        // Refresh the strategies to show the updated status
        fetchStrategies();
      } else {
        console.error('Failed to toggle strategy');
      }
    } catch (error) {
      console.error('Network error toggling strategy:', error);
    }
  };

  const addNewStrategy = () => {
    alert('Adding new strategies is a complex feature and requires backend implementation. This is a placeholder.');
  };

  return (
    <div className="strategies-tab">
      <div className="tab-header">
        <h2>Strategy Management</h2>
        <button onClick={addNewStrategy} className="btn-primary">Add New Strategy</button>
      </div>

      <div className="strategies-grid">
        {loading ? (
          <p>Loading strategies...</p>
        ) : strategies.length > 0 ? (
          strategies.map((strategy) => (
            <div key={strategy.id} className="strategy-card">
              <h3>{strategy.name}</h3>
              <p>Status: <span className={strategy.is_active ? 'text-success' : 'text-danger'}>{strategy.is_active ? 'Active' : 'Inactive'}</span></p>
              <p>Win Rate: {strategy.win_rate.toFixed(2)}%</p>
              <p>Total Trades: {strategy.total_trades}</p>
              <p>P/L: <span className={strategy.pnl >= 0 ? 'text-success' : 'text-danger'}>${strategy.pnl.toFixed(2)}</span></p>
              <button onClick={() => toggleStrategy(strategy.id)} className={strategy.is_active ? 'btn-warning' : 'btn-success'}>
                {strategy.is_active ? 'Disable' : 'Enable'}
              </button>
            </div>
          ))
        ) : (
          <p>No strategies found.</p>
        )}
      </div>
    </div>
  );
};

export default StrategiesTab;
