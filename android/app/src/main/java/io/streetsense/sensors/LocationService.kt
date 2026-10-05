package io.streetsense.sensors

import android.annotation.SuppressLint
import android.content.Context
import android.location.Location
import android.location.LocationManager
import android.os.Looper
import com.google.android.gms.location.*
import io.streetsense.domain.model.LocationSnapshot
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

class LocationService(private val context: Context) {
    private val fusedClient: FusedLocationProviderClient =
        LocationServices.getFusedLocationProviderClient(context)
    private val locationManager =
        context.getSystemService(Context.LOCATION_SERVICE) as LocationManager

    private val _locationFlow = MutableSharedFlow<LocationSnapshot>(extraBufferCapacity = 32)
    val locationFlow: SharedFlow<LocationSnapshot> = _locationFlow.asSharedFlow()

    @Volatile
    private var isTracking = false

    private val locationCallback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            val location: Location = result.lastLocation ?: return
            val snapshot = LocationSnapshot(
                latitude = location.latitude,
                longitude = location.longitude,
                altitude = if (location.hasAltitude()) location.altitude else null,
                accuracy_meters = location.accuracy,
                speed_mps = if (location.hasSpeed()) location.speed else null,
                bearing_degrees = if (location.hasBearing()) location.bearing else null,
                timestamp_ns = location.elapsedRealtimeNanos,
                wall_clock_timestamp_ms = System.currentTimeMillis(),
                is_available = true
            )
            _locationFlow.tryEmit(snapshot)
        }

        override fun onLocationAvailability(availability: LocationAvailability) {
            if (!availability.isLocationAvailable) {
                val unavailableSnapshot = LocationSnapshot(
                    latitude = 0.0,
                    longitude = 0.0,
                    accuracy_meters = null,
                    timestamp_ns = System.nanoTime(),
                    wall_clock_timestamp_ms = System.currentTimeMillis(),
                    is_available = false
                )
                _locationFlow.tryEmit(unavailableSnapshot)
            }
        }
    }

    fun isGpsHardwareEnabled(): Boolean {
        return locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER) ||
               locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
    }

    @SuppressLint("MissingPermission")
    fun startTracking(hasPermission: Boolean) {
        if (!hasPermission || isTracking) {
            if (!hasPermission) {
                // Emit unavailable due to permission denial
                _locationFlow.tryEmit(
                    LocationSnapshot(
                        latitude = 0.0,
                        longitude = 0.0,
                        accuracy_meters = null,
                        timestamp_ns = System.nanoTime(),
                        is_available = false
                    )
                )
            }
            return
        }

        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 2000L)
            .setMinUpdateIntervalMillis(1000L)
            .setWaitForAccurateLocation(false)
            .build()

        fusedClient.requestLocationUpdates(request, locationCallback, Looper.getMainLooper())
        isTracking = true
    }

    fun stopTracking() {
        if (!isTracking) return
        fusedClient.removeLocationUpdates(locationCallback)
        isTracking = false
    }
}
