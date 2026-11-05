package io.streetsense.data

import android.content.Context
import androidx.room.*

@Entity(tableName = "local_events")
data class LocalEventEntity(
    @PrimaryKey val event_id: String,
    val session_id: String,
    val category: String,
    val severity: String,
    val timestamp_ns: Long,
    val explanation: String,
    val haptic_pattern: String,
    val latitude: Double?,
    val longitude: Double?,
    val is_synced: Boolean = false
)

@Entity(tableName = "sync_queue")
data class SyncQueueEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val message_id: String,
    val event_type: String,
    val payload_json: String,
    val created_at_ms: Long = System.currentTimeMillis(),
    val attempts: Int = 0
)

@Dao
interface EventDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertEvent(event: LocalEventEntity)

    @Query("SELECT * FROM local_events ORDER BY timestamp_ns DESC LIMIT 50")
    suspend fun getRecentEvents(): List<LocalEventEntity>

    @Query("UPDATE local_events SET is_synced = 1 WHERE event_id = :eventId")
    suspend fun markSynced(eventId: String)
}

@Dao
interface SyncQueueDao {
    @Insert
    suspend fun enqueue(item: SyncQueueEntity)

    @Query("SELECT * FROM sync_queue ORDER BY id ASC LIMIT 20")
    suspend fun getPendingBatch(): List<SyncQueueEntity>

    @Query("DELETE FROM sync_queue WHERE id = :id")
    suspend fun dequeue(id: Long)

    @Query("SELECT COUNT(*) FROM sync_queue")
    suspend fun getQueueCount(): Int

    @Query("DELETE FROM sync_queue WHERE id IN (SELECT id FROM sync_queue ORDER BY id ASC LIMIT :count)")
    suspend fun trimOldest(count: Int)
}

@Database(entities = [LocalEventEntity::class, SyncQueueEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun eventDao(): EventDao
    abstract fun syncQueueDao(): SyncQueueDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "streetsense_offline.db"
                ).build()
                INSTANCE = instance
                instance
            }
        }
    }
}
