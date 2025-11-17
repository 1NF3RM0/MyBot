import React, { useState, useEffect } from 'react';
import './App.css';

// Placeholder components for different tabs
const Monitor = ({ logs }) => (
    <div className="tab-content">
        <h2>Live Monitor</h2>
        <div className="log-container">
            {logs.map((log, index) => (
                <div key={index} className="log-message">{log}</div>
            ))}
        </div>
    </div>
);

const Settings = () => {
    const [config, setConfig] = useState({ APP_ID: '', API_TOKEN: '' });

    useEffect(() => {
        fetch('http://localhost:8000/config')
            .then(res => res.json())
            .then(data => setConfig(data));
    }, []);

    const handleChange = (e) => {
        setConfig({ ...config, [e.target.name]: e.target.value });
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        fetch('http://localhost:8000/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });
    };

    return (
        <div className="tab-content">
            <h2>Settings</h2>
            <form onSubmit={handleSubmit}>
                <div className="form-group">
                    <label>Deriv App ID</label>
                    <input type="text" name="APP_ID" value={config.APP_ID} onChange={handleChange} />
                </div>
                <div className="form-group">
                    <label>Deriv API Token</label>
                    <input type="password" name="API_TOKEN" value={config.API_TOKEN} onChange={handleChange} />
                </div>
                <button type="submit">Save Settings</button>
            </form>
        </div>
    );
};

const Confidence = () => (
    <div className="tab-content">
        <h2>Strategy Confidence</h2>
        <p>Confidence scores for each strategy will be displayed here.</p>
        {/* This will be populated with data from the bot */}
    </div>
);


function App() {
    const [activeTab, setActiveTab] = useState('monitor');
    const [botStatus, setBotStatus] = useState('stopped');
    const [logs, setLogs] = useState([]);

    useEffect(() => {
        // Fetch initial bot status
        fetch('http://localhost:8000/bot/status')
            .then(res => res.json())
            .then(data => setBotStatus(data.status));

        // Setup WebSocket connection
        const ws = new WebSocket('ws://localhost:8000/ws');
        ws.onmessage = (event) => {
            setLogs(prevLogs => [...prevLogs, event.data]);
            if (event.data.includes("started")) {
                setBotStatus('running');
            }
            if (event.data.includes("stopped")) {
                setBotStatus('stopped');
            }
        };

        return () => {
            ws.close();
        };
    }, []);

    const startBot = () => {
        fetch('http://localhost:8000/bot/start', { method: 'POST' });
    };

    const stopBot = () => {
        fetch('http://localhost:8000/bot/stop', { method: 'POST' });
    };

    const renderTabContent = () => {
        switch (activeTab) {
            case 'monitor':
                return <Monitor logs={logs} />;
            case 'settings':
                return <Settings />;
            case 'confidence':
                return <Confidence />;
            default:
                return <Monitor logs={logs} />;
        }
    };

    return (
        <div className="App">
            <header className="App-header">
                <h1>MyBot Control Panel</h1>
                <div className="bot-controls">
                    <button onClick={startBot} disabled={botStatus === 'running'}>Start Bot</button>
                    <button onClick={stopBot} disabled={botStatus === 'stopped'}>Stop Bot</button>
                    <span className={`status-indicator ${botStatus}`}>
                        Status: {botStatus}
                    </span>
                </div>
            </header>
            <nav className="App-nav">
                <button onClick={() => setActiveTab('monitor')} className={activeTab === 'monitor' ? 'active' : ''}>Monitor</button>
                <button onClick={() => setActiveTab('settings')} className={activeTab === 'settings' ? 'active' : ''}>Settings</button>
                <button onClick={() => setActiveTab('confidence')} className={activeTab === 'confidence' ? 'active' : ''}>Confidence</button>
            </nav>
            <main className="App-main">
                {renderTabContent()}
            </main>
        </div>
    );
}

export default App;