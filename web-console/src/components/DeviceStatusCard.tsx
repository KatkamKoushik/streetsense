import React from 'react';
import { BatteryCharging, Battery, Thermometer, Wifi, Cpu } from 'lucide-react';
import { DeviceStatusPayload } from '../types/protocol';

interface DeviceStatusCardProps {
  deviceStatus: DeviceStatusPayload | null;
  deviceId: string | null;
}

export const DeviceStatusCard: React.FC<DeviceStatusCardProps> = ({ deviceStatus, deviceId }) => {
  if (!deviceStatus) {
    return (
      <div className="glass-panel" style={{ padding: '20px', minHeight: '180px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
        <Cpu size={32} color="var(--text-subtle)" style={{ marginBottom: '10px' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-main)', marginBottom: '4px' }}>Edge Hardware State</h3>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Awaiting device status telemetry (Zero-Mock Data Active)
        </p>
      </div>
    );
  }

  const isLowBattery = deviceStatus.battery_level < 20;

  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={18} color="var(--accent-cyan)" />
          Hardware & Telemetry State
        </h3>
        <span style={{ fontSize: '12px', color: 'var(--text-subtle)', fontFamily: 'var(--font-mono)' }}>
          {deviceId || 'Connected Device'}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        {/* Battery */}
        <div className="glass-panel-subtle" style={{ padding: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '12px', marginBottom: '6px' }}>
            {deviceStatus.is_charging ? <BatteryCharging size={16} color="var(--accent-emerald)" /> : <Battery size={16} color={isLowBattery ? 'var(--accent-rose)' : 'var(--text-main)'} />}
            <span>Battery</span>
          </div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: isLowBattery ? 'var(--accent-rose)' : 'var(--text-main)' }}>
            {deviceStatus.battery_level.toFixed(0)}%
          </div>
        </div>

        {/* Temperature */}
        <div className="glass-panel-subtle" style={{ padding: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '12px', marginBottom: '6px' }}>
            <Thermometer size={16} color="var(--accent-amber)" />
            <span>Battery Temp</span>
          </div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)' }}>
            {deviceStatus.battery_temperature_c.toFixed(1)}°C
          </div>
        </div>

        {/* Thermal State */}
        <div className="glass-panel-subtle" style={{ padding: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '12px', marginBottom: '6px' }}>
            <span>Thermal Mode</span>
          </div>
          <div style={{
            fontSize: '13px',
            fontWeight: 700,
            color: deviceStatus.thermal_state === 'NORMAL' ? 'var(--accent-emerald)' : 'var(--accent-rose)'
          }}>
            {deviceStatus.thermal_state}
          </div>
        </div>

        {/* Network */}
        <div className="glass-panel-subtle" style={{ padding: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '12px', marginBottom: '6px' }}>
            <Wifi size={16} color="var(--accent-cyan)" />
            <span>Network</span>
          </div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-main)' }}>
            {deviceStatus.network_type}
          </div>
        </div>
      </div>

      {/* Active Sensor Pills */}
      <div>
        <div style={{ fontSize: '12px', color: 'var(--text-subtle)', marginBottom: '8px' }}>ACTIVE HARDWARE SENSORS</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {deviceStatus.active_sensors && deviceStatus.active_sensors.length > 0 ? (
            deviceStatus.active_sensors.map((sensor) => (
              <span key={sensor} style={{
                fontSize: '11px',
                padding: '3px 8px',
                borderRadius: '6px',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                color: 'var(--accent-emerald)',
                fontFamily: 'var(--font-mono)'
              }}>
                {sensor}
              </span>
            ))
          ) : (
            <span style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>None reported</span>
          )}
        </div>
      </div>
    </div>
  );
};
