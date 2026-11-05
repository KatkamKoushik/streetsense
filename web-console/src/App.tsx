import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { DeviceStatusCard } from './components/DeviceStatusCard';
import { TelemetryChart } from './components/TelemetryChart';
import { ExpertExecutionTimeline } from './components/ExpertExecutionTimeline';
import { AlertIncidentFeed } from './components/AlertIncidentFeed';
import { SpatialMap } from './components/SpatialMap';
import { wsClient } from './services/websocket';
import {
  WsMessageEnvelope, EventType, DeviceStatusPayload,
  SensorSnapshot, ExpertResult, DetectedEvent, LocationSnapshot
} from './types/protocol';

export const App: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [latencyMs, setLatencyMs] = useState(0);
  const [authError, setAuthError] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeDeviceId, setActiveDeviceId] = useState<string | null>(null);

  const [deviceStatus, setDeviceStatus] = useState<DeviceStatusPayload | null>(null);
  const [snapshots, setSnapshots] = useState<SensorSnapshot[]>([]);
  const [expertRuns, setExpertRuns] = useState<ExpertResult[]>([]);
  const [events, setEvents] = useState<DetectedEvent[]>([]);
  const [location, setLocation] = useState<LocationSnapshot | null>(null);

  useEffect(() => {
    // Acquire authenticated token and load initial events
    const initData = async () => {
      try {
        const token = await wsClient.acquireToken();
        const res = await fetch('/api/v1/events?limit=20', {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            setEvents(data.map((e) => ({
              event_id: e.event_id,
              session_id: e.session_id,
              timestamp_ns: e.timestamp_ns,
              category: e.category,
              severity: e.severity,
              confidence_breakdown: e.confidence_breakdown,
              contributing_evidence_ids: e.contributing_evidence_ids,
              explanation: e.explanation,
              haptic_pattern: e.haptic_pattern,
              latitude: e.latitude,
              longitude: e.longitude,
              is_dismissed: e.is_dismissed
            })));
          }
        }
      } catch (err: any) {
        console.warn('Initial REST fetch notice:', err.message);
      }
    };

    initData();

    // Connect WebSocket
    wsClient.connect();

    const unsubStatus = wsClient.onStatusChange((connected, latency) => {
      setIsConnected(connected);
      setLatencyMs(latency);
    });

    const unsubError = wsClient.onError((errorMsg) => {
      setAuthError(errorMsg);
    });

    const unsubMessages = wsClient.subscribe((envelope: WsMessageEnvelope) => {
      if (envelope.session_id) setActiveSessionId(envelope.session_id);
      if (envelope.device_id) setActiveDeviceId(envelope.device_id);

      const payload = envelope.payload;
      if (!payload) return;

      switch (envelope.event_type) {
        case EventType.DEVICE_STATUS:
          if (payload.device_status) {
            setDeviceStatus(payload.device_status);
          }
          break;

        case EventType.SENSOR_STATUS:
          if (payload.snapshots && Array.isArray(payload.snapshots)) {
            setSnapshots((prev) => [...prev.slice(-100), ...payload.snapshots]);
          }
          if (payload.location) {
            setLocation(payload.location);
          }
          break;

        case EventType.EXPERT_COMPLETED:
        case EventType.INFERENCE_COMPLETED:
          if (payload.expert_result) {
            setExpertRuns((prev) => [payload.expert_result, ...prev.slice(0, 30)]);
          }
          break;

        case EventType.EVENT_DETECTED:
        case EventType.ALERT_TRIGGERED:
          if (payload.event) {
            setEvents((prev) => [payload.event, ...prev.filter((e) => e.event_id !== payload.event.event_id)]);
          }
          break;

        default:
          break;
      }
    });

    return () => {
      unsubStatus();
      unsubError();
      unsubMessages();
      wsClient.disconnect();
    };
  }, []);

  const handleDismissAlert = async (eventId: string) => {
    try {
      const token = await wsClient.acquireToken();
      await fetch(`/api/v1/events/${eventId}/dismiss`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      setEvents((prev) => prev.map((e) => (e.event_id === eventId ? { ...e, is_dismissed: true } : e)));
    } catch (e) {
      console.error('Failed to dismiss event', e);
    }
  };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px' }}>
      <Header
        isConnected={isConnected}
        latencyMs={latencyMs}
        activeSessionId={activeSessionId}
        activeDeviceId={activeDeviceId}
      />

      {authError && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.15)',
          color: '#fca5a5',
          padding: '12px 20px',
          borderRadius: '8px',
          marginBottom: '20px',
          border: '1px solid rgba(239, 68, 68, 0.4)',
          fontSize: '14px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          <strong>Security Warning:</strong> {authError}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: '20px' }}>
        {/* Left Column: Telemetry & Hardware Status */}
        <div style={{ gridColumn: 'span 7', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <DeviceStatusCard deviceStatus={deviceStatus} deviceId={activeDeviceId} />
          <TelemetryChart snapshots={snapshots} />
          <SpatialMap location={location} />
        </div>

        {/* Right Column: Expert Waterfall & Hazard Feeds */}
        <div style={{ gridColumn: 'span 5', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <AlertIncidentFeed events={events.filter((e) => !e.is_dismissed)} onDismiss={handleDismissAlert} />
          <ExpertExecutionTimeline expertRuns={expertRuns} />
        </div>
      </div>
    </div>
  );
};
