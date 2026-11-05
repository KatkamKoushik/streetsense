package io.streetsense.data

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonObject
import io.streetsense.domain.model.EventType
import io.streetsense.domain.model.WsMessageEnvelope
import kotlinx.coroutines.*
import okhttp3.*
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong

class StreetSenseWebSocketClient(
    private var serverUrl: String,
    private val deviceId: String,
    private var authToken: String? = null,
    private val db: AppDatabase? = null,
    private val onConnectionChanged: ((Boolean) -> Unit)? = null,
    private val onAuthError: ((String) -> Unit)? = null
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
    var isAuthenticated = false
        private set

    @Volatile
    private var isIntentionalClose = false
    private var reconnectAttempt = 0

    fun updateAuthToken(token: String?) {
        authToken = token
        if (isConnected) {
            disconnect()
            connect()
        }
    }

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

        val requestBuilder = Request.Builder().url(serverUrl)

        // Transport bearer token in header rather than exposing in URL query string
        authToken?.let { token ->
            requestBuilder.addHeader("Authorization", "Bearer $token")
            requestBuilder.addHeader("Sec-WebSocket-Protocol", "bearer.$token")
        }

        val request = requestBuilder.build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                reconnectAttempt = 0
                Log.i("StreetSenseWS", "TCP WebSocket open to: $serverUrl")

                // Transmit first-frame auth envelope if token available
                authToken?.let { token ->
                    val authFrame = JsonObject().apply {
                        addProperty("event_type", "auth")
                        addProperty("token", token)
                    }
                    webSocket.send(gson.toJson(authFrame))
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = gson.fromJson(text, JsonObject::class.java)
                    val eventType = json.get("event_type")?.asString

                    if (eventType == "auth.success") {
                        isAuthenticated = true
                        isConnected = true
                        Log.i("StreetSenseWS", "Authenticated successfully as $deviceId")
                        onConnectionChanged?.invoke(true)
                        flushOfflineQueue()
                        return
                    }

                    if (eventType == "auth.error") {
                        isAuthenticated = false
                        isConnected = false
                        val errorDetail = json.get("error")?.asString ?: "Authentication failed"
                        Log.e("StreetSenseWS", "Authentication rejected by gateway: $errorDetail")
                        onAuthError?.invoke(errorDetail)
                        return
                    }

                    if (eventType == "server.draining") {
                        val reason = json.get("reason")?.asString ?: "Server undergoing maintenance"
                        Log.w("StreetSenseWS", "Server draining connection (33-B014): $reason")
                        return
                    }

                    Log.d("StreetSenseWS", "Received message from gateway: $text")
                } catch (e: Exception) {
                    Log.d("StreetSenseWS", "Received text: $text")
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                isConnected = false
                isAuthenticated = false
                Log.i("StreetSenseWS", "Connection closed: $reason ($code)")
                onConnectionChanged?.invoke(false)

                if (code == 4401 || code == 4403 || code == 1008) {
                    onAuthError?.invoke("Connection rejected ($code): $reason")
                    return
                }

                scheduleReconnect()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                isConnected = false
                isAuthenticated = false
                val code = response?.code ?: 0
                Log.w("StreetSenseWS", "Connection failure (code $code): ${t.message}")
                onConnectionChanged?.invoke(false)

                if (code == 401 || code == 403) {
                    onAuthError?.invoke("HTTP Handshake failed with status $code: Unauthorized")
                    return
                }

                scheduleReconnect()
            }
        })
    }

    private fun scheduleReconnect() {
        if (isIntentionalClose) return
        // Checklist 33-N010: Exponential backoff with randomized jitter to prevent reconnect storms
        val baseDelayMs = (1000L * Math.pow(1.5, reconnectAttempt.toDouble()).toLong()).coerceAtMost(10000L)
        val jitterMs = (Math.random() * 500).toLong()
        val delayMs = (baseDelayMs + jitterMs).coerceAtMost(15000L)
        reconnectAttempt++
        clientScope.launch {
            delay(delayMs)
            if (!isConnected && !isIntentionalClose) {
                Log.i("StreetSenseWS", "Reconnecting to gateway (attempt $reconnectAttempt, delay ${delayMs}ms)...")
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
            timestamp_ns = System.currentTimeMillis() * 1_000_000L,
            event_type = eventType.wireName,
            sequence_number = seq,
            payload = payload
        )

        val json = gson.toJson(envelope)

        if (isConnected && isAuthenticated && webSocket != null) {
            val sent = webSocket?.send(json) ?: false
            if (sent) return true
        }

        // If offline or sending fails, enqueue to local Room database for reliable sync
        if (db != null) {
            clientScope.launch {
                try {
                    // Checklist 20-N005: Bound queued operations (FIFO eviction of oldest items when queue exceeds max capacity)
                    val currentCount = db.syncQueueDao().getQueueCount()
                    if (currentCount >= 5000) {
                        val toTrim = currentCount - 5000 + 1
                        db.syncQueueDao().trimOldest(toTrim)
                        Log.w("StreetSenseWS", "Offline queue reached capacity (5000). Evicted $toTrim oldest items (FIFO).")
                    }
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
        if (db == null || !isAuthenticated) return
        clientScope.launch {
            try {
                val pending = db.syncQueueDao().getPendingBatch()
                if (pending.isNotEmpty()) {
                    Log.i("StreetSenseWS", "Flushing ${pending.size} pending offline queue items...")
                    for (item in pending) {
                        if (!isConnected || !isAuthenticated || webSocket == null) break
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
        isAuthenticated = false
        onConnectionChanged?.invoke(false)
    }
}
