import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

const SettingsTab = () => {
  const { token, logout } = useAuth();
  const [apiConfig, setApiConfig] = useState({ deriv_app_id: '', deriv_api_token: '' });
  const [riskConfig, setRiskConfig] = useState({ risk_percentage: 2.0, stop_loss_percent: 10.0, take_profit_percent: 20.0 });
  const [notificationConfig, setNotificationConfig] = useState({ email: '', notifications_enabled: false });
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState(''); // 'success' or 'error'

  const fetchSettings = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8000/config', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setApiConfig({
          deriv_app_id: data.deriv_app_id || '',
          deriv_api_token: data.deriv_api_token || '',
        });
        setRiskConfig({
          risk_percentage: data.risk_percentage || 2.0,
          stop_loss_percent: data.stop_loss_percent || 10.0,
          take_profit_percent: data.take_profit_percent || 20.0,
        });
        setNotificationConfig({
          email: data.email || '', // Assuming email is part of user settings
          notifications_enabled: data.notifications_enabled || false,
        });
      } else {
        console.error('Failed to fetch settings');
      }
    } catch (error) {
      console.error('Network error fetching settings:', error);
    }
  }, [token]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleApiConfigChange = (e) => {
    setApiConfig({ ...apiConfig, [e.target.name]: e.target.value });
  };

  const handleRiskConfigChange = (e) => {
    setRiskConfig({ ...riskConfig, [e.target.name]: parseFloat(e.target.value) });
  };

  const handleNotificationChange = (e) => {
    const { name, value, type, checked } = e.target;
    setNotificationConfig({
      ...notificationConfig,
      [name]: type === 'checkbox' ? checked : value,
    });
  };

  const saveSettings = async (settingsType) => {
    let payload = {};
    if (settingsType === 'api') {
      payload = apiConfig;
    } else if (settingsType === 'risk') {
      payload = riskConfig;
    } else if (settingsType === 'notifications') {
      payload = notificationConfig;
    }

    try {
      const response = await fetch('http://localhost:8000/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        setMessage('Settings saved successfully!');
        setMessageType('success');
      } else {
        const errorData = await response.json();
        setMessage(`Failed to save settings: ${errorData.detail || response.statusText}`);
        setMessageType('error');
      }
    } catch (error) {
      setMessage(`Network error: ${error.message}`);
      setMessageType('error');
    }
  };

  const resetAllData = async () => {
    if (window.confirm('WARNING: This will permanently delete ALL your trade data and settings. Are you absolutely sure?')) {
      try {
        const response = await fetch('http://localhost:8000/user/reset', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (response.ok) {
          alert('Your data has been reset. You will now be logged out.');
          logout();
        } else {
          const errorData = await response.json();
          setMessage(`Failed to reset data: ${errorData.detail || response.statusText}`);
          setMessageType('error');
        }
      } catch (error) {
        setMessage(`Network error: ${error.message}`);
        setMessageType('error');
      }
    }
  };

  return (
    <div className="settings-tab">
      <h2>Settings</h2>
      {message && <div className={`alert ${messageType}`}>{message}</div>}

      <div className="settings-section">
        <h3>API Configuration</h3>
        <div className="form-group">
          <label>Deriv App ID</label>
          <input
            type="text"
            name="deriv_app_id"
            value={apiConfig.deriv_app_id}
            onChange={handleApiConfigChange}
          />
        </div>
        <div className="form-group">
          <label>Deriv API Token</label>
          <input
            type="password"
            name="deriv_api_token"
            value={apiConfig.deriv_api_token}
            onChange={handleApiConfigChange}
          />
        </div>
        <button onClick={() => saveSettings('api')}>Save API Settings</button>
      </div>

      <div className="settings-section">
        <h3>Risk Management</h3>
        <div className="form-group">
          <label>Risk Percentage (%)</label>
          <input
            type="number"
            name="risk_percentage"
            value={riskConfig.risk_percentage}
            onChange={handleRiskConfigChange}
            step="0.1"
          />
        </div>
        <div className="form-group">
          <label>Stop Loss Percentage (%)</label>
          <input
            type="number"
            name="stop_loss_percent"
            value={riskConfig.stop_loss_percent}
            onChange={handleRiskConfigChange}
            step="0.1"
          />
        </div>
        <div className="form-group">
          <label>Take Profit Percentage (%)</label>
          <input
            type="number"
            name="take_profit_percent"
            value={riskConfig.take_profit_percent}
            onChange={handleRiskConfigChange}
            step="0.1"
          />
        </div>
        <button onClick={() => saveSettings('risk')}>Save Risk Settings</button>
      </div>

      <div className="settings-section">
        <h3>Notifications</h3>
        <div className="form-group">
          <label>Email for Alerts</label>
          <input
            type="email"
            name="email"
            value={notificationConfig.email}
            onChange={handleNotificationChange}
          />
        </div>
        <div className="form-group checkbox-group">
          <input
            type="checkbox"
            name="notifications_enabled"
            checked={notificationConfig.notifications_enabled}
            onChange={handleNotificationChange}
            id="enableNotifications"
          />
          <label htmlFor="enableNotifications">Enable Email Notifications</label>
        </div>
        <button onClick={() => saveSettings('notifications')}>Save Notification Settings</button>
      </div>

      <div className="settings-section danger-zone">
        <h3>Danger Zone</h3>
        <p>Proceed with caution. These actions are irreversible.</p>
        <button onClick={resetAllData} className="btn-danger">Reset All Data</button>
      </div>
    </div>
  );
};

export default SettingsTab;
