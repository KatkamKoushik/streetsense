import { WsMessageEnvelope, EventType } from '../types/protocol';

export type MessageHandler = (envelope: WsMessageEnvelope) => void;
export type StatusHandler = (connected: boolean, latencyMs: number) => void;
export type ErrorHandler = (errorMsg: string | null) => void;

export class ConsoleWebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private token: string | null = null;
  private apiKey: string;
  private messageListeners: Set<MessageHandler> = new Set();
  private statusListeners: Set<StatusHandler> = new Set();
  private errorListeners: Set<ErrorHandler> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 20;
  private isIntentionalClose = false;
  private pingIntervalId: any = null;
  private lastPingTime = 0;
  public latencyMs = 0;
  public isConnected = false;
  public isAuthenticated = false;
  public lastError: string | null = null;

  constructor(
    url?: string,
    apiKey: string = 'streetsense_dev_console_access_key_32c'
  ) {
    if (url) {
      this.url = url;
    } else if (typeof window !== 'undefined' && window.location && window.location.host) {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      this.url = `${proto}//${window.location.host}/ws/console`;
    } else {
      this.url = 'ws://127.0.0.1:8000/ws/console';
    }
    this.apiKey = (typeof localStorage !== 'undefined' ? localStorage.getItem('streetsense_console_key') : null) || apiKey;
  }

  public setApiKey(key: string): void {
    this.apiKey = key;
    localStorage.setItem('streetsense_console_key', key);
    this.token = null;
    if (this.isConnected) {
      this.disconnect();
      this.connect();
    }
  }

  public getApiKey(): string {
    return this.apiKey;
  }

  public async acquireToken(): Promise<string> {
    if (this.token) return this.token;
    try {
      const res = await fetch('/api/v1/auth/console-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: this.apiKey, client_id: 'web_console_ui' }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Authentication failed' }));
        throw new Error(err.detail || 'Failed to acquire console token');
      }
      const data = await res.json();
      this.token = data.access_token;
      return this.token!;
    } catch (e: any) {
      const msg = e.message || 'Token acquisition failed';
      this.notifyError(msg);
      throw e;
    }
  }

  public async connect(): Promise<void> {
    this.isIntentionalClose = false;
    this.notifyError(null);

    let token: string;
    try {
      token = await this.acquireToken();
    } catch (e: any) {
      console.error('Cannot connect WebSocket: Token acquisition failed', e);
      this.scheduleReconnect();
      return;
    }

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        // Transmit first-frame authentication envelope immediately
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({
            event_type: 'auth',
            token: token
          }));
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Auth handshake response
          if (data.event_type === 'auth.success') {
            this.isAuthenticated = true;
            this.isConnected = true;
            this.notifyError(null);
            this.notifyStatus(true, this.latencyMs);
            this.startHeartbeat();
            return;
          }

          if (data.event_type === 'auth.error') {
            this.isAuthenticated = false;
            this.notifyError(data.error || 'Authentication error from server');
            this.token = null; // Invalidate cached token
            return;
          }

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

      this.ws.onclose = (event) => {
        this.isConnected = false;
        this.isAuthenticated = false;
        this.stopHeartbeat();
        this.notifyStatus(false, 0);

        if (event.code === 4401 || event.code === 4403 || event.code === 1008) {
          this.notifyError(`Access denied by server (${event.code}). Please check your console credentials.`);
          this.token = null;
        }

        if (!this.isIntentionalClose) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (err) => {
        console.warn('WebSocket connection error:', err);
      };
    } catch (e: any) {
      console.error('WebSocket connection setup failed:', e);
      this.notifyError(e.message || 'Connection setup failed');
      this.scheduleReconnect();
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingIntervalId = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN && this.isAuthenticated) {
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

  public onError(handler: ErrorHandler): () => void {
    this.errorListeners.add(handler);
    handler(this.lastError);
    return () => this.errorListeners.delete(handler);
  }

  private notifyStatus(connected: boolean, latency: number): void {
    this.statusListeners.forEach((handler) => handler(connected, latency));
  }

  private notifyError(errorMsg: string | null): void {
    this.lastError = errorMsg;
    this.errorListeners.forEach((handler) => handler(errorMsg));
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

export const wsClient = new ConsoleWebSocketClient();
