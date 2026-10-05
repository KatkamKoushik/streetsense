import React from 'react';
import { Activity, Radio, ShieldAlert } from 'lucide-react';

interface HeaderProps {
  isConnected: boolean;
  latencyMs: number;
  activeSessionId: string | null;
  activeDeviceId: string | null;
}

export const Header: React.FC<HeaderProps> = ({
  isConnected,
  latencyMs,
  activeSessionId,
  activeDeviceId
}) => {
  return (
    <header className="glass-panel" style={{ padding: '16px 24px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div style={{
          width: '42px',
          height: '42px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 15px rgba(2, 132, 199, 0.4)'
        }}>
          <ShieldAlert size={24} color="#ffffff" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h1 style={{ fontSize: '20px', fontWeight: 700, letterSpacing: '-0.5px' }}>StreetSense</h1>
            <span style={{
              fontSize: '11px',
              padding: '2px 8px',
              borderRadius: '6px',
              background: 'rgba(56, 189, 248, 0.15)',
              color: 'var(--accent-cyan)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              fontWeight: 600
            }}>
              OFFICE KIT
            </span>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Real-Time Edge Observation & Multi-Expert Alert Console
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-muted)' }}>
          <Radio size={16} color={activeDeviceId ? "var(--accent-cyan)" : "var(--text-subtle)"} />
          <span>Device: <strong style={{ color: activeDeviceId ? "var(--text-main)" : "var(--text-subtle)" }}>
            {activeDeviceId || "No live device connected"}
          </strong></span>
        </div>

        {activeSessionId && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-muted)' }}>
            <Activity size={16} color="var(--accent-emerald)" />
            <span>Session: <strong style={{ color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>{activeSessionId.slice(0, 14)}...</strong></span>
          </div>
        )}

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 14px',
          borderRadius: '20px',
          background: isConnected ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
          border: isConnected ? '1px solid rgba(16, 185, 129, 0.25)' : '1px solid rgba(244, 63, 94, 0.25)'
        }}>
          <span className={`status-dot ${isConnected ? 'status-dot-active' : 'status-dot-offline'}`} />
          <span style={{ fontSize: '13px', fontWeight: 600, color: isConnected ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
            {isConnected ? `CONNECTED (${latencyMs}ms)` : 'DISCONNECTED'}
          </span>
        </div>
      </div>
    </header>
  );
};
