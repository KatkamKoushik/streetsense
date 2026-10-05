import React from 'react';
import { Layers, Clock } from 'lucide-react';
import { ExpertResult, ExecutionStatus } from '../types/protocol';

interface ExpertExecutionTimelineProps {
  expertRuns: ExpertResult[];
}

export const ExpertExecutionTimeline: React.FC<ExpertExecutionTimelineProps> = ({ expertRuns }) => {
  if (expertRuns.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '20px', minHeight: '220px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
        <Layers size={32} color="var(--text-subtle)" style={{ marginBottom: '10px' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-main)', marginBottom: '4px' }}>Selective Expert Waterfall</h3>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Awaiting expert executions from edge device (Zero-Mock Data Active)
        </p>
      </div>
    );
  }

  const getStatusColor = (status: ExecutionStatus) => {
    switch (status) {
      case ExecutionStatus.SUCCESS:
        return 'var(--accent-emerald)';
      case ExecutionStatus.DEGRADED:
        return 'var(--accent-amber)';
      case ExecutionStatus.UNAVAILABLE:
      case ExecutionStatus.NOT_IMPLEMENTED:
        return 'var(--text-subtle)';
      case ExecutionStatus.FAILED:
      case ExecutionStatus.TIMEOUT:
        return 'var(--accent-rose)';
      default:
        return 'var(--accent-cyan)';
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} color="var(--accent-cyan)" />
            Selective Expert Execution Waterfall
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>
            Capability-driven invocation latency and model confidence
          </p>
        </div>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Total Runs: <strong style={{ color: 'var(--text-main)' }}>{expertRuns.length}</strong>
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '320px', overflowY: 'auto', paddingRight: '4px' }}>
        {expertRuns.slice(0, 15).map((run, idx) => {
          const statusColor = getStatusColor(run.status);
          return (
            <div
              key={`${run.expert_id}_${run.timestamp_ns}_${idx}`}
              className="glass-panel-subtle"
              style={{ padding: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span
                  style={{
                    width: '6px',
                    height: '32px',
                    borderRadius: '3px',
                    backgroundColor: statusColor
                  }}
                />
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>
                      {run.expert_id}
                    </span>
                    <span style={{
                      fontSize: '10px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: 'rgba(56, 189, 248, 0.1)',
                      color: 'var(--accent-cyan)',
                      fontFamily: 'var(--font-mono)'
                    }}>
                      {run.capability}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                    <span>Status: <strong style={{ color: statusColor }}>{run.status}</strong></span>
                    {run.prediction && (
                      <span>• Prediction: <strong style={{ color: 'var(--text-main)' }}>{run.prediction}</strong></span>
                    )}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                {/* Confidence Bar */}
                <div style={{ width: '80px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)' }}>
                    <span>Conf</span>
                    <span>{(run.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div style={{ width: '100%', height: '4px', borderRadius: '2px', background: 'rgba(148, 163, 184, 0.15)', overflow: 'hidden' }}>
                    <div style={{ width: `${run.confidence * 100}%`, height: '100%', backgroundColor: statusColor, borderRadius: '2px' }} />
                  </div>
                </div>

                {/* Latency */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', color: 'var(--text-muted)', minWidth: '60px' }}>
                  <Clock size={14} color="var(--text-subtle)" />
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{run.latency_ms.toFixed(1)}ms</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
