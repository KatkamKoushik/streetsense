package io.streetsense.engine

import io.streetsense.domain.model.SensorSnapshot
import io.streetsense.domain.model.SensorType
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

class TemporalRingBuffer(private val capacity: Int = 120) {
    private val buffer = ArrayList<SensorSnapshot>(capacity)
    private val lock = ReentrantLock()

    fun push(snapshot: SensorSnapshot) {
        lock.withLock {
            if (buffer.size >= capacity) {
                buffer.removeAt(0)
            }
            buffer.add(snapshot)
        }
    }

    fun getRecent(limit: Int = 50): List<SensorSnapshot> {
        lock.withLock {
            val count = buffer.size.coerceAtMost(limit)
            return buffer.takeLast(count)
        }
    }

    fun getRecentByType(type: SensorType, limit: Int = 30): List<SensorSnapshot> {
        lock.withLock {
            return buffer.filter { it.sensor_type == type }.takeLast(limit)
        }
    }

    fun clear() {
        lock.withLock {
            buffer.clear()
        }
    }

    fun size(): Int {
        lock.withLock {
            return buffer.size
        }
    }
}
