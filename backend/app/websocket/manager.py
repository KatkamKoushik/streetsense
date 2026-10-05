import json
import logging
from collections import OrderedDict
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger("streetsense.websocket")


class ConnectionManager:
    def __init__(self, max_dedup_cache_size: int = 10000):
        self.active_devices: Dict[str, WebSocket] = {}
        self.active_observers: Set[WebSocket] = set()
        self._seen_message_ids: OrderedDict[str, bool] = OrderedDict()
        self._max_dedup_cache_size = max_dedup_cache_size

    async def connect_device(self, device_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_devices[device_id] = websocket
        logger.info(f"Edge device connected: {device_id} (Total devices: {len(self.active_devices)})")

    def disconnect_device(self, device_id: str) -> None:
        if device_id in self.active_devices:
            del self.active_devices[device_id]
            logger.info(f"Edge device disconnected: {device_id} (Total devices: {len(self.active_devices)})")

    async def connect_observer(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_observers.add(websocket)
        logger.info(f"Office Kit observer connected (Total observers: {len(self.active_observers)})")

    def disconnect_observer(self, websocket: WebSocket) -> None:
        if websocket in self.active_observers:
            self.active_observers.remove(websocket)
            logger.info(f"Office Kit observer disconnected (Total observers: {len(self.active_observers)})")

    def is_duplicate(self, message_id: str) -> bool:
        if message_id in self._seen_message_ids:
            return True
        self._seen_message_ids[message_id] = True
        if len(self._seen_message_ids) > self._max_dedup_cache_size:
            self._seen_message_ids.popitem(last=False)
        return False

    async def broadcast_to_observers(self, message: Dict[str, Any]) -> None:
        if not self.active_observers:
            return
        payload_text = json.dumps(message)
        dead_observers = set()
        for ws in self.active_observers:
            try:
                await ws.send_text(payload_text)
            except Exception as e:
                logger.warning(f"Error sending to observer: {e}")
                dead_observers.add(ws)

        for dead in dead_observers:
            self.disconnect_observer(dead)


ws_manager = ConnectionManager()
