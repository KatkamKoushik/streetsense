import json
import time
import asyncio
import logging
from collections import OrderedDict
from typing import Dict, Set, Any, Optional, List
from fastapi import WebSocket

logger = logging.getLogger("streetsense.websocket.manager")


class ConnectionManager:
    def __init__(self, max_dedup_cache_size: int = 10000, observer_timeout_seconds: float = 1.5):
        self.active_devices: Dict[str, WebSocket] = {}
        self.active_observers: Set[WebSocket] = set()
        self._seen_message_ids: OrderedDict[str, float] = OrderedDict()
        self._max_dedup_cache_size = max_dedup_cache_size
        self._rate_limits: Dict[str, List[float]] = {}
        self._session_sequences: Dict[str, int] = {}
        self.observer_timeout_seconds = observer_timeout_seconds

    async def connect_device(self, device_id: str, websocket: WebSocket) -> None:
        self.active_devices[device_id] = websocket
        logger.info(f"Authenticated device connection registered: {device_id} (Active devices: {len(self.active_devices)})")

    def disconnect_device(self, device_id: str) -> None:
        if device_id in self.active_devices:
            del self.active_devices[device_id]
            logger.info(f"Device disconnected: {device_id} (Active devices: {len(self.active_devices)})")
        if device_id in self._rate_limits:
            del self._rate_limits[device_id]

    async def connect_observer(self, websocket: WebSocket) -> None:
        self.active_observers.add(websocket)
        logger.info(f"Authenticated console observer connected (Active observers: {len(self.active_observers)})")

    def disconnect_observer(self, websocket: WebSocket) -> None:
        if websocket in self.active_observers:
            self.active_observers.remove(websocket)
            logger.info(f"Console observer disconnected (Active observers: {len(self.active_observers)})")

    def is_duplicate(self, message_id: str) -> bool:
        """Check and record message ID for deduplication."""
        now = time.time()
        if message_id in self._seen_message_ids:
            return True
        self._seen_message_ids[message_id] = now
        if len(self._seen_message_ids) > self._max_dedup_cache_size:
            self._seen_message_ids.popitem(last=False)
        return False

    def check_rate_limit(self, identifier: str, limit_per_minute: int) -> bool:
        """Sliding-window per-minute rate limit check. Returns True if within limit."""
        now = time.time()
        window_start = now - 60.0
        timestamps = self._rate_limits.setdefault(identifier, [])
        # Prune older than 60s
        self._rate_limits[identifier] = [t for t in timestamps if t > window_start]
        if len(self._rate_limits[identifier]) >= limit_per_minute:
            return False
        self._rate_limits[identifier].append(now)
        return True

    def validate_and_update_sequence(self, session_id: str, sequence_number: int) -> bool:
        """
        Enforce strictly monotonic sequence numbers per session to prevent replay or out-of-order ingress.
        """
        last_seq = self._session_sequences.get(session_id)
        if last_seq is not None and sequence_number <= last_seq:
            logger.warning(
                f"Sequence anomaly on session {session_id}: incoming {sequence_number} <= previous {last_seq}"
            )
            return False
        self._session_sequences[session_id] = sequence_number
        return True

    async def broadcast_to_observers(self, message: Dict[str, Any]) -> None:
        """
        Broadcast sanitized message to authorized observer sessions.
        Enforces slow-consumer bounding (33-N006): slow or stalled consumers that fail
        to consume within the timeout window are evicted to protect server memory.
        """
        if not self.active_observers:
            return
        payload_text = json.dumps(message)
        dead_observers = set()
        for ws in list(self.active_observers):
            try:
                await asyncio.wait_for(ws.send_text(payload_text), timeout=self.observer_timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning("Slow consumer detected on observer websocket; terminating slow connection to protect server memory (33-N006).")
                dead_observers.add(ws)
                try:
                    await ws.close(code=1008, reason="Slow consumer evicted")
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Error broadcasting to observer: {e}")
                dead_observers.add(ws)

        for dead in dead_observers:
            self.disconnect_observer(dead)

    async def drain_all(self, reason: str = "server.draining", code: int = 1001) -> None:
        """
        Gracefully drain and close all active device and observer connections (33-B014).
        Sends a draining notification frame before issuing close code 1001 (Going Away).
        """
        drain_frame = json.dumps({"event_type": "server.draining", "reason": reason})

        # Drain devices
        devices = list(self.active_devices.items())
        for device_id, ws in devices:
            try:
                await asyncio.wait_for(ws.send_text(drain_frame), timeout=0.5)
                await ws.close(code=code, reason=reason)
            except Exception:
                pass
            self.disconnect_device(device_id)

        # Drain observers
        observers = list(self.active_observers)
        for ws in observers:
            try:
                await asyncio.wait_for(ws.send_text(drain_frame), timeout=0.5)
                await ws.close(code=code, reason=reason)
            except Exception:
                pass
            self.disconnect_observer(ws)

        logger.info(f"Graceful drain complete: drained {len(devices)} devices and {len(observers)} observers.")


ws_manager = ConnectionManager()
