import { WsMessageEnvelope, EventType } from '../types/protocol';

export type MessageHandler = (envelope: WsMessageEnvelope) => void;
export type StatusHandler = (connected: boolean, latencyMs: number) => void;

class OfficeKitWebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private messageListeners: Set<MessageHandler> = new Set();
  private statusListeners: Set<StatusHandler> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 50;
  private isIntentionalClose = false;
  private pingIntervalId: any = null;
  private lastPingTime = 0;
  public latencyMs = 0;
  public isConnected = false;

  constructor(url: string = 'ws://127.0.0.1:8000/ws/office-kit') {
    this.url = url;
  }

  public connect(): void {
    this.isIntentionalClose = false;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.notifyStatus(true, this.latencyMs);
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event_type === EventType.HEARTBEAT_PONG) {
            this.latencyMs = Math.max(1, Math.round((performance.now() - this.lastPingTime)));
            this.notifyStatus(true, this.latencyMs);
            return;
          }
          this.messageListeners.forEach((listener) => listener(data));
        } catch (e) {
          console.error('Failed to parse WebSocket message', e);
        }
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this.stopHeartbeat();
        this.notifyStatus(false, 0);
        if (!this.isIntentionalClose) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (err) => {
        console.warn('WebSocket connection error:', err);
      };
    } catch (e) {
      console.error('WebSocket connection setup failed:', e);
      this.scheduleReconnect();
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingIntervalId = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.lastPingTime = performance.now();
        this.ws.send(JSON.stringify({
          event_type: EventType.HEARTBEAT_PING,
          timestamp_ns: Date.now() * 1000000
        }));
      }
    }, 4000);
  }

  private stopHeartbeat(): void {
    if (this.pingIntervalId) {
      clearInterval(this.pingIntervalId);
      this.pingIntervalId = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
    const delay = Math.min(10000, 1000 * Math.pow(1.5, this.reconnectAttempts));
    this.reconnectAttempts++;
    setTimeout(() => {
      if (!this.isConnected && !this.isIntentionalClose) {
        this.connect();
      }
    }, delay);
  }

  public subscribe(handler: MessageHandler): () => void {
    this.messageListeners.add(handler);
    return () => this.messageListeners.delete(handler);
  }

  public onStatusChange(handler: StatusHandler): () => void {
    this.statusListeners.add(handler);
    handler(this.isConnected, this.latencyMs);
    return () => this.statusListeners.delete(handler);
  }

  private notifyStatus(connected: boolean, latency: number): void {
    this.statusListeners.forEach((h) => h(connected, latency));
  }

  public disconnect(): void {
    this.isIntentionalClose = true;
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const wsClient = new OfficeKitWebSocketClient();
