import React, { useEffect, useRef } from 'react';
import { LineChart as LineChartIcon } from 'lucide-react';
import { SensorSnapshot, SensorType } from '../types/protocol';

interface TelemetryChartProps {
  snapshots: SensorSnapshot[];
}

export const TelemetryChart: React.FC<TelemetryChartProps> = ({ snapshots }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const accelSnapshots = snapshots.filter((s) => s.sensor_type === SensorType.ACCELEROMETER);
  const latestSnapshot = accelSnapshots.length > 0 ? accelSnapshots[accelSnapshots.length - 1] : null;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    if (accelSnapshots.length < 2) {
      return;
    }

    // Draw grid lines
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.08)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let y = 20; y < height; y += 30) {
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
    }
    ctx.stroke();

    // Baseline 0g in center
    const centerY = height / 2;
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)';
    ctx.beginPath();
    ctx.moveTo(0, centerY);
    ctx.lineTo(width, centerY);
    ctx.stroke();

    const maxSamples = 60;
    const recent = accelSnapshots.slice(-maxSamples);
    const stepX = width / (maxSamples - 1);

    // Scale: 40 m/s^2 maps to half height
    const scaleY = (height / 2) / 35.0;

    // Helper to draw series
    const drawSeries = (axisIndex: number, color: string) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      recent.forEach((snap, idx) => {
        const val = snap.values[axisIndex] || 0;
        const x = idx * stepX;
        const y = centerY - val * scaleY;
        if (idx === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();
    };

    drawSeries(0, '#f43f5e'); // X: Red
    drawSeries(1, '#10b981'); // Y: Green
    drawSeries(2, '#38bdf8'); // Z: Cyan
  }, [accelSnapshots]);

  if (accelSnapshots.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '20px', minHeight: '260px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
        <LineChartIcon size={32} color="var(--text-subtle)" style={{ marginBottom: '10px' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-main)', marginBottom: '4px' }}>Real-Time IMU Telemetry</h3>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Awaiting live accelerometer data stream (Zero-Mock Data Active)
        </p>
      </div>
    );
  }

  const curX = latestSnapshot ? latestSnapshot.values[0]?.toFixed(2) : '0.00';
  const curY = latestSnapshot ? latestSnapshot.values[1]?.toFixed(2) : '0.00';
  const curZ = latestSnapshot ? latestSnapshot.values[2]?.toFixed(2) : '0.00';

  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <LineChartIcon size={18} color="var(--accent-cyan)" />
            Real-Time Accelerometer Dynamics
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>
            Kinetic magnitude and multi-axis shock analysis (±35 m/s²)
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
          <span style={{ color: '#f43f5e' }}>X: {curX}</span>
          <span style={{ color: '#10b981' }}>Y: {curY}</span>
          <span style={{ color: '#38bdf8' }}>Z: {curZ}</span>
        </div>
      </div>

      <div style={{ width: '100%', height: '170px', position: 'relative' }}>
        <canvas
          ref={canvasRef}
          width={650}
          height={170}
          style={{ width: '100%', height: '100%', display: 'block', borderRadius: '8px' }}
        />
      </div>
    </div>
  );
};
