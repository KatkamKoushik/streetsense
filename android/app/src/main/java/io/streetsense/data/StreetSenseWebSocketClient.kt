package io.streetsense.data

import android.util.Log
import com.google.gson.Gson
import io.streetsense.domain.model.EventType
import io.streetsense.domain.model.WsMessageEnvelope
import kotlinx.coroutines.*
import okhttp3.*
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong

class StreetSenseWebSocketClient(
    private var serverUrl: String,
    private val deviceId: String,
    private val db: AppDatabase? = null,
    private val onConnectionChanged: ((Boolean) -> Unit)? = null
) {
    private val client = OkHttpClient.Builder()
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .pingInterval(4, TimeUnit.SECONDS)
        .build()

    private val gson = Gson()
    private var webSocket: WebSocket? = null
    private val sequenceNumber = AtomicLong(1)
    private val clientScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    @Volatile
    var isConnected = false
        private set

    @Volatile
    private var isIntentionalClose = false
    private var reconnectAttempt = 0

    fun updateServerUrl(newUrl: String) {
        if (serverUrl != newUrl) {
            serverUrl = newUrl
            if (isConnected) {
                disconnect()
                connect()
            }
        }
    }

    fun getServerUrl(): String = serverUrl

    fun connect() {
        isIntentionalClose = false
        val fullUrl = if (serverUrl.contains("?")) "$serverUrl&device_id=$deviceId" else "$serverUrl?device_id=$deviceId"
        val request = Request.Builder().url(fullUrl).build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                isConnected = true
                reconnectAttempt = 0
                Log.i("StreetSenseWS", "Connected to realtime gateway at: $serverUrl")
                onConnectionChanged?.invoke(true)

                // Flush pending offline sync queue upon successful connection
                flushOfflineQueue()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d("StreetSenseWS", "Received message from gateway: $text")
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                isConnected = false
                Log.i("StreetSenseWS", "Connection closed: $reason ($code)")
                onConnectionChanged?.invoke(false)
                scheduleReconnect()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                isConnected = false
                Log.w("StreetSenseWS", "Connection failure: ${t.message}")
                onConnectionChanged?.invoke(false)
                scheduleReconnect()
            }
        })
    }

    private fun scheduleReconnect() {
        if (isIntentionalClose) return
        val delayMs = (1000L * Math.pow(1.5, reconnectAttempt.toDouble()).toLong()).coerceAtMost(10000L)
        reconnectAttempt++
        clientScope.launch {
            delay(delayMs)
            if (!isConnected && !isIntentionalClose) {
                Log.i("StreetSenseWS", "Reconnecting to gateway (attempt $reconnectAttempt)...")
                connect()
            }
        }
    }

    fun <T> sendEnvelope(
        eventType: EventType,
        sessionId: String,
        payload: T,
        correlationId: String = "corr_${System.currentTimeMillis()}"
    ): Boolean {
        val seq = sequenceNumber.getAndIncrement()
        val envelope = WsMessageEnvelope(
            message_id = "msg_${System.currentTimeMillis()}_$seq",
            correlation_id = correlationId,
            session_id = sessionId,
            device_id = deviceId,
            timestamp_ns = System.nanoTime(),
            event_type = eventType.wireName,
            sequence_number = seq,
            payload = payload
        )

        val json = gson.toJson(envelope)

        if (isConnected && webSocket != null) {
            val sent = webSocket?.send(json) ?: false
            if (sent) return true
        }

        // If offline or sending fails, enqueue to local Room database for reliable sync
        if (db != null) {
            clientScope.launch {
                try {
                    db.syncQueueDao().enqueue(
                        SyncQueueEntity(
                            message_id = envelope.message_id,
                            event_type = envelope.event_type,
                            payload_json = json
                        )
                    )
                    Log.d("StreetSenseWS", "Enqueued unsent message ${envelope.message_id} to offline SQLite queue")
                } catch (e: Exception) {
                    Log.e("StreetSenseWS", "Failed to enqueue offline message", e)
                }
            }
        }
        return false
    }

    private fun flushOfflineQueue() {
        if (db == null) return
        clientScope.launch {
            try {
                val pending = db.syncQueueDao().getPendingBatch()
                if (pending.isNotEmpty()) {
                    Log.i("StreetSenseWS", "Flushing ${pending.size} pending offline queue items...")
                    for (item in pending) {
                        if (!isConnected || webSocket == null) break
                        val sent = webSocket?.send(item.payload_json) ?: false
                        if (sent) {
                            db.syncQueueDao().dequeue(item.id)
                        } else {
                            break
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e("StreetSenseWS", "Error flushing offline queue", e)
            }
        }
    }

    fun disconnect() {
        isIntentionalClose = true
        webSocket?.close(1000, "User initiated disconnect")
        webSocket = null
        isConnected = false
        onConnectionChanged?.invoke(false)
    }
}
