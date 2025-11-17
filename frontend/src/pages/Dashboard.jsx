import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import '../App.css';

// Import tab components
import DashboardTab from '../components/DashboardTab';
import StrategiesTab from '../components/StrategiesTab';
import TradeLogTab from '../components/TradeLogTab';
import SettingsTab from '../components/SettingsTab';

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const { logout, token } = useAuth();
  const [ws, setWs] = useState(null);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    if (token) {
      const webSocket = new WebSocket(`ws://localhost:8000/ws/${token}`);
      webSocket.onmessage = (event) => {
        setLogs(prevLogs => [event.data, ...prevLogs]);
      };
      setWs(webSocket);

      return () => {
        webSocket.close();
      };
    }
  }, [token]);

  const renderTabContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardTab logs={logs} />;
      case 'strategies':
        return <StrategiesTab />;
      case 'tradelog':
        return <TradeLogTab />;
      case 'settings':
        return <SettingsTab />;
      default:
        return <DashboardTab logs={logs} />;
    }
  };

  return (
    <div className="app-container">
      <aside className="sidebar">
        <h1 className="logo">MyBot</h1>
        <nav className="sidebar-nav">
          <button onClick={() => setActiveTab('dashboard')} className={activeTab === 'dashboard' ? 'active' : ''}>Dashboard</button>
          <button onClick={() => setActiveTab('strategies')} className={activeTab === 'strategies' ? 'active' : ''}>Strategies</button>
          <button onClick={() => setActiveTab('tradelog')} className={activeTab === 'tradelog' ? 'active' : ''}>Trade Log</button>
          <button onClick={() => setActiveTab('settings')} className={activeTab === 'settings' ? 'active' : ''}>Settings</button>
        </nav>
        <div className="sidebar-footer">
          <button onClick={logout}>Logout</button>
        </div>
      </aside>
      <main className="main-content">
        {renderTabContent()}
      </main>
    </div>
  );
};

export default Dashboard;
