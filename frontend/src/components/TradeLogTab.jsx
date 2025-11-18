import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

const TradeLogTab = () => {
  const { token } = useAuth();
  const [trades, setTrades] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStrategy, setFilterStrategy] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [uniqueStrategies, setUniqueStrategies] = useState([]);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const fetchTradeLogs = useCallback(async (reset = false) => {
    if (!hasMore && !reset) return;

    const currentPage = reset ? 0 : page;
    const params = new URLSearchParams({
      skip: currentPage * 50,
      limit: 50,
    });
    if (searchTerm) params.append('search', searchTerm);
    if (filterStrategy !== 'all') params.append('strategy', filterStrategy);
    if (filterStatus !== 'all') params.append('status', filterStatus);

    try {
      const response = await fetch(`http://localhost:8000/tradelog?${params.toString()}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setTrades(prev => reset ? data : [...prev, ...data]);
        setHasMore(data.length === 50);
        if (reset) setPage(1); else setPage(p => p + 1);
      }
    } catch (error) {
      console.error('Error fetching trade logs:', error);
    }
  }, [token, searchTerm, filterStrategy, filterStatus, page, hasMore]);

  useEffect(() => {
    setTrades([]);
    setPage(0);
    setHasMore(true);
    // This effect will trigger a fetch when filters change
  }, [searchTerm, filterStrategy, filterStatus]);

  useEffect(() => {
    fetchTradeLogs(true);
  }, [searchTerm, filterStrategy, filterStatus]); // Re-fetch when filters change

  useEffect(() => {
    // Fetch unique strategies for the filter dropdown
    const fetchStrategies = async () => {
      try {
        const response = await fetch('http://localhost:8000/strategies', {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          setUniqueStrategies([...new Set(data.map(s => s.id))]);
        }
      } catch (error) {
        console.error('Error fetching strategies for filter:', error);
      }
    };
    fetchStrategies();
  }, [token]);

  const exportToCSV = () => {
    const params = new URLSearchParams();
    if (searchTerm) params.append('search', searchTerm);
    if (filterStrategy !== 'all') params.append('strategy', filterStrategy);
    if (filterStatus !== 'all') params.append('status', filterStatus);
    
    const url = `http://localhost:8000/tradelog/export?${params.toString()}`;
    
    // Create a temporary anchor element to trigger the download
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.setAttribute('download', 'trade_log.csv');
    // We need to add the token to the request, which is not possible with a direct link.
    // A backend that supports tokens in query params is one way, but for now, we'll use fetch.
    fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(res => res.blob())
      .then(blob => {
        const blobUrl = window.URL.createObjectURL(blob);
        anchor.href = blobUrl;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        window.URL.revokeObjectURL(blobUrl);
      });
  };

  return (
    <div className="tradelog-tab">
      <div className="tab-header">
        <h2>Trade History</h2>
        <button onClick={exportToCSV} className="btn-primary">Export to CSV</button>
      </div>

      <div className="filters-section">
        <input
          type="text"
          placeholder="Search by symbol..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
        <select value={filterStrategy} onChange={(e) => setFilterStrategy(e.target.value)} className="filter-select">
          <option value="all">All Strategies</option>
          {uniqueStrategies.map(strategy => (
            <option key={strategy} value={strategy}>{strategy}</option>
          ))}
        </select>
        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="filter-select">
          <option value="all">All Statuses</option>
          <option value="Open">Open</option>
          <option value="Closed (Win)">Closed (Win)</option>
          <option value="Closed (Loss)">Closed (Loss)</option>
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
            {trades.length > 0 ? (
              trades.map(trade => (
                <tr key={trade.id}>
                  <td>{new Date(trade.timestamp).toLocaleString()}</td>
                  <td>{trade.symbol}</td>
                  <td>{trade.strategy}</td>
                  <td>{trade.type}</td>
                  <td>{trade.entry_price ? trade.entry_price.toFixed(5) : 'N/A'}</td>
                  <td>{trade.exit_price ? trade.exit_price.toFixed(5) : 'N/A'}</td>
                  <td className={(trade.status === 'Open' ? trade.current_pnl : trade.pnl) >= 0 ? 'text-success' : 'text-danger'}>
                    {trade.status === 'Open' ? (trade.current_pnl ? `$${trade.current_pnl.toFixed(2)}` : 'N/A') : (trade.pnl ? `$${trade.pnl.toFixed(2)}` : 'N/A')}
                  </td>
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
      {hasMore && (
        <div style={{ textAlign: 'center', marginTop: '1rem' }}>
          <button onClick={() => fetchTradeLogs()} className="btn-secondary">Load More</button>
        </div>
      )}
    </div>
  );
};

export default TradeLogTab;
