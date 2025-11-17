import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

const TradeLogTab = () => {
  const { token } = useAuth();
  const [trades, setTrades] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStrategy, setFilterStrategy] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');

  const fetchTradeLogs = useCallback(async () => {
    // This endpoint needs to be created in the backend
    // It should return a list of trade logs for the current user
    // For now, using dummy data
    const dummyTradeLogs = [
      { id: 1, timestamp: '2025-11-18 10:30:00', symbol: 'EURUSD', strategy: 'Golden Cross', type: 'CALL', entry: 1.08500, exit: 1.08550, pnl: 5.00, status: 'Closed (Win)' },
      { id: 2, timestamp: '2025-11-18 10:25:00', symbol: 'GBPUSD', strategy: 'RSI Dip', type: 'PUT', entry: 1.25000, exit: 1.25020, pnl: -2.00, status: 'Closed (Loss)' },
      { id: 3, timestamp: '2025-11-18 10:20:00', symbol: 'AUDUSD', strategy: 'MACD Crossover', type: 'CALL', entry: 0.68000, exit: null, pnl: null, status: 'Open' },
      { id: 4, timestamp: '2025-11-18 10:15:00', symbol: 'EURUSD', strategy: 'Golden Cross', type: 'PUT', entry: 1.08600, exit: 1.08580, pnl: 2.00, status: 'Closed (Win)' },
    ];
    setTrades(dummyTradeLogs);
  }, []);

  useEffect(() => {
    fetchTradeLogs();
  }, [fetchTradeLogs]);

  const handleSearchChange = (e) => {
    setSearchTerm(e.target.value);
  };

  const handleStrategyFilterChange = (e) => {
    setFilterStrategy(e.target.value);
  };

  const handleStatusFilterChange = (e) => {
    setFilterStatus(e.target.value);
  };

  const exportToCSV = () => {
    // This would typically involve an API call to the backend to generate the CSV
    // For now, we'll just log a message
    alert('Exporting trade history to CSV is not yet implemented.');
    console.log('Exporting filtered trades to CSV...');
  };

  const filteredTrades = trades.filter(trade => {
    const matchesSearch = trade.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          trade.strategy.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStrategy = filterStrategy === 'all' || trade.strategy === filterStrategy;
    const matchesStatus = filterStatus === 'all' || trade.status.toLowerCase().includes(filterStatus.toLowerCase());
    return matchesSearch && matchesStrategy && matchesStatus;
  });

  // Extract unique strategies for filter dropdown
  const uniqueStrategies = [...new Set(trades.map(trade => trade.strategy))];

  return (
    <div className="tradelog-tab">
      <div className="tab-header">
        <h2>Trade History</h2>
        <button onClick={exportToCSV} className="btn-primary">Export to CSV</button>
      </div>

      <div className="filters-section">
        <input
          type="text"
          placeholder="Search by symbol or strategy..."
          value={searchTerm}
          onChange={handleSearchChange}
          className="search-input"
        />
        <select value={filterStrategy} onChange={handleStrategyFilterChange} className="filter-select">
          <option value="all">All Strategies</option>
          {uniqueStrategies.map(strategy => (
            <option key={strategy} value={strategy}>{strategy}</option>
          ))}
        </select>
        <select value={filterStatus} onChange={handleStatusFilterChange} className="filter-select">
          <option value="all">All Statuses</option>
          <option value="open">Open</option>
          <option value="closed (win)">Closed (Win)</option>
          <option value="closed (loss)">Closed (Loss)</option>
        </select>
      </div>

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
            {filteredTrades.length > 0 ? (
              filteredTrades.map(trade => (
                <tr key={trade.id}>
                  <td>{trade.timestamp}</td>
                  <td>{trade.symbol}</td>
                  <td>{trade.strategy}</td>
                  <td>{trade.type}</td>
                  <td>{trade.entry ? trade.entry.toFixed(5) : 'N/A'}</td>
                  <td>{trade.exit ? trade.exit.toFixed(5) : 'N/A'}</td>
                  <td className={trade.pnl >= 0 ? 'text-success' : 'text-danger'}>{trade.pnl ? `$${trade.pnl.toFixed(2)}` : 'N/A'}</td>
                  <td>{trade.status}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="8" style={{ textAlign: 'center' }}>No trades found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TradeLogTab;
