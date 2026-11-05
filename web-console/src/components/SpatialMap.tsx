import React from 'react';
import { MapPin, Navigation, Compass } from 'lucide-react';
import { LocationSnapshot } from '../types/protocol';

interface SpatialMapProps {
  location: LocationSnapshot | null;
}

export const SpatialMap: React.FC<SpatialMapProps> = ({ location }) => {
  if (!location) {
    return (
      <div className="glass-panel" style={{ padding: '20px', minHeight: '220px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
        <MapPin size={32} color="var(--text-subtle)" style={{ marginBottom: '10px' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-main)', marginBottom: '4px' }}>Geospatial Tracking</h3>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Awaiting GPS / location coordinates (Zero-Mock Data Active)
        </p>
      </div>
    );
  }

  const speedKmh = location.speed_mps ? (location.speed_mps * 3.6).toFixed(1) : '0.0';

  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MapPin size={18} color="var(--accent-cyan)" />
            Geospatial & Kinematic State
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>
            Real-time coordinates, velocity, and bearing tracking
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <div className="glass-panel-subtle" style={{ padding: '12px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginBottom: '4px' }}>COORDINATES</div>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
            {location.latitude.toFixed(5)}, {location.longitude.toFixed(5)}
          </div>
        </div>

        <div className="glass-panel-subtle" style={{ padding: '12px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginBottom: '4px' }}>ACCURACY</div>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>
            ±{location.accuracy_meters.toFixed(1)} meters
          </div>
        </div>

        <div className="glass-panel-subtle" style={{ padding: '12px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Navigation size={12} />
            <span>GROUND SPEED</span>
          </div>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-main)' }}>
            {speedKmh} km/h
          </div>
        </div>

        <div className="glass-panel-subtle" style={{ padding: '12px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Compass size={12} />
            <span>BEARING</span>
          </div>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>
            {location.bearing_degrees !== undefined ? `${location.bearing_degrees.toFixed(0)}°` : 'N/A'}
          </div>
        </div>
      </div>
    </div>
  );
};
