import React from 'react';
import { AlertTriangle, CheckCircle, Info, ShieldAlert, ChevronDown, ChevronUp } from 'lucide-react';
import { DetectedEvent, EventSeverity } from '../types/protocol';

interface AlertIncidentFeedProps {
  events: DetectedEvent[];
  onDismiss: (eventId: string) => void;
}

export const AlertIncidentFeed: React.FC<AlertIncidentFeedProps> = ({ events, onDismiss }) => {
  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  if (events.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '20px', minHeight: '260px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
        <CheckCircle size={32} color="var(--accent-emerald)" style={{ marginBottom: '10px' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-main)', marginBottom: '4px' }}>Incident & Hazard Stream</h3>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          No hazards detected on active stream (Zero-Mock Data Active)
        </p>
      </div>
    );
  }

  const getSeverityStyle = (severity: EventSeverity) => {
    switch (severity) {
      case EventSeverity.CRITICAL:
        return {
          border: '1px solid rgba(244, 63, 94, 0.4)',
          bg: 'rgba(244, 63, 94, 0.1)',
          color: 'var(--accent-rose)',
          icon: <ShieldAlert size={18} color="var(--accent-rose)" />
        };
      case EventSeverity.HIGH_RISK:
        return {
          border: '1px solid rgba(244, 63, 94, 0.3)',
          bg: 'rgba(244, 63, 94, 0.08)',
          color: 'var(--accent-rose)',
          icon: <AlertTriangle size={18} color="var(--accent-rose)" />
        };
      case EventSeverity.WARNING:
        return {
          border: '1px solid rgba(245, 158, 11, 0.3)',
          bg: 'rgba(245, 158, 11, 0.08)',
          color: 'var(--accent-amber)',
          icon: <AlertTriangle size={18} color="var(--accent-amber)" />
        };
      case EventSeverity.NOTICE:
      case EventSeverity.INFO:
      default:
        return {
          border: '1px solid rgba(56, 189, 248, 0.3)',
          bg: 'rgba(56, 189, 248, 0.08)',
          color: 'var(--accent-cyan)',
          icon: <Info size={18} color="var(--accent-cyan)" />
        };
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={18} color="var(--accent-amber)" />
            Real-Time Hazard & Incident Stream
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>
            Deterministic events synthesized through multi-modal evidence fusion
          </p>
        </div>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Incidents: <strong style={{ color: 'var(--text-main)' }}>{events.length}</strong>
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '420px', overflowY: 'auto', paddingRight: '4px' }}>
        {events.map((evt) => {
          const style = getSeverityStyle(evt.severity);
          const isExpanded = expandedId === evt.event_id;
          return (
            <div
              key={evt.event_id}
              data-testid={`event-card-${evt.event_id}`}
              className="glass-panel-subtle"
              style={{
                border: style.border,
                backgroundColor: style.bg,
                padding: '14px',
                borderRadius: '10px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {style.icon}
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-main)' }}>
                        {evt.category}
                      </span>
                      <span style={{
                        fontSize: '10px',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        backgroundColor: 'rgba(0, 0, 0, 0.3)',
                        color: style.color,
                        fontWeight: 700
                      }}>
                        {evt.severity}
                      </span>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    data-testid={`dismiss-${evt.event_id}`}
                    onClick={() => onDismiss(evt.event_id)}
                    style={{
                      background: 'rgba(148, 163, 184, 0.15)',
                      border: '1px solid rgba(148, 163, 184, 0.25)',
                      color: 'var(--text-main)',
                      borderRadius: '6px',
                      padding: '4px 10px',
                      fontSize: '11px',
                      cursor: 'pointer'
                    }}
                  >
                    Dismiss
                  </button>
                  <button
                    onClick={() => toggleExpand(evt.event_id)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center'
                    }}
                  >
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                </div>
              </div>

              {/* Grounded Local Reasoning Explanation */}
              <p style={{ fontSize: '13px', color: 'var(--text-main)', lineHeight: '1.4', marginBottom: '8px' }}>
                {evt.explanation}
              </p>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px', color: 'var(--text-muted)' }}>
                <span>Confidence: <strong style={{ color: style.color }}>{(evt.confidence_breakdown.final_decision_confidence * 100).toFixed(0)}%</strong></span>
                <span>Haptic: <strong style={{ color: 'var(--text-main)', fontFamily: 'var(--font-mono)' }}>{evt.haptic_pattern}</strong></span>
              </div>

              {/* Collapsible Evidence Breakdown */}
              {isExpanded && (
                <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(148, 163, 184, 0.15)' }}>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
                    MULTI-FACTOR CONFIDENCE BREAKDOWN
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px', fontSize: '11px', color: 'var(--text-subtle)', marginBottom: '10px' }}>
                    <div>Prediction: {(evt.confidence_breakdown.prediction_confidence * 100).toFixed(0)}%</div>
                    <div>Input Quality: {(evt.confidence_breakdown.input_quality * 100).toFixed(0)}%</div>
                    <div>Agreement: {(evt.confidence_breakdown.cross_expert_agreement * 100).toFixed(0)}%</div>
                    <div>Sensor Reliability: {(evt.confidence_breakdown.sensor_reliability * 100).toFixed(0)}%</div>
                  </div>

                  {evt.contributing_evidence && evt.contributing_evidence.length > 0 && (
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
                        CORROBORATING EVIDENCE ITEMS
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {evt.contributing_evidence.map((item) => (
                          <div key={item.evidence_id} style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between', background: 'rgba(0,0,0,0.2)', padding: '4px 8px', borderRadius: '4px' }}>
                            <span>{item.evidence_type} ({item.source_sensor})</span>
                            <span style={{ color: 'var(--accent-cyan)' }}>{(item.confidence * 100).toFixed(0)}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
