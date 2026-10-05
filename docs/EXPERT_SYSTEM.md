# StreetSense — Expert System Specification

## 1. Core Architectural Principle: Selective Multi-Expert

StreetSense departs fundamentally from monolithic edge AI approaches. In a monolithic model, deep convolutional or transformer networks run continuously on every video frame regardless of environmental state, rapidly draining battery, inducing thermal throttling, and producing opaque single-score predictions.

StreetSense enforces a **Selective Multi-Expert Architecture**:
1. **Capabilities over Models**: The system routes work by required capability (e.g. `MOTION_ANALYSIS`, `OBJECT_DETECTION`, `ROAD_ANALYSIS`), decoupling orchestration from model implementations.
2. **Deterministic-First**: Inexpensive, deterministic sensor heuristics and lightweight specialists run first.
3. **Evidence-Driven Escalation**: Expensive specialists (e.g. vision networks, high-resolution spatial models) execute only when lower-tier evidence exhibits anomalies, high risk, or critical uncertainty.
4. **Separation of Concerns**:
   $$\text{Detection} \longrightarrow \text{Interpretation} \longrightarrow \text{Evidence Fusion} \longrightarrow \text{Arbitration} \longrightarrow \text{Decision} \longrightarrow \text{Explanation}$$
   An LLM or ML classifier is never the sole arbiter of a safety decision.

---

## 2. Expert Abstraction Contract

Every expert in the system implements the canonical `Expert` interface:

```kotlin
interface Expert {
    val id: String
    val capabilities: Set<Capability>
    val supportedInputTypes: Set<InputType>
    val requiredSensors: Set<SensorType>
    val estimatedLatencyMs: Long
    val estimatedEnergyCost: EnergyCostTier // VERY_LOW, LOW, MEDIUM, HIGH, CRITICAL
    val limitations: List<String>
    val provenance: ModelProvenance

    suspend fun isAvailable(context: ExecutionContext): AvailabilityStatus
    suspend fun execute(request: ExpertExecutionRequest): ExpertResult
}
```

### Expert Result Contract

```kotlin
data class ExpertResult(
    val expertId: String,
    val status: ExecutionStatus, // SUCCESS, DEGRADED, FAILED, TIMEOUT, SKIPPED
    val capability: Capability,
    val prediction: String,
    val confidence: Double, // [0.0, 1.0]
    val evidenceList: List<EvidenceItem>,
    val timestampMs: Long,
    val latencyMs: Long,
    val provenance: ModelProvenance,
    val limitations: List<String>,
    val errorDetails: String? = null
)
```

### Evidence Item Contract

```kotlin
data class EvidenceItem(
    val evidenceId: String,
    val sourceExpertId: String,
    val sensorSource: SensorType,
    val timestampMs: Long,
    val evidenceType: EvidenceType, // SENSOR_READING, MOTION_VECTOR, BOUNDING_BOX, TEMPORAL_PERSISTENCE, SPATIAL_PROXIMITY, SCENE_CLASSIFICATION
    val confidence: Double,
    val payloadJson: String, // Typed JSON data matching evidenceType schema
    val qualityScore: Double,
    val temporalWindowMs: Long? = null
)
```

---

## 3. Capability Taxonomy & Expert Registry Matrix

| Capability | Initial Expert Implementation | Inputs Required | Energy Cost | Typical Latency | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SENSOR_QUALITY` | `SensorQualityExpert` | Raw sensor stream rates, variance | VERY_LOW | < 2 ms | Detects sensor drops, noise, jitter, and occlusions |
| `MOTION_ANALYSIS` | `MotionExpert` | Accelerometer, Gyroscope 50Hz buffer | LOW | < 5 ms | Detects walking, running, sudden stops, falls, rapid turn |
| `LOCATION_ANALYSIS` | `LocationExpert` | Fused Location (lat, lon, speed, bearing) | LOW | < 5 ms | Evaluates speed, heading stability, transit mode |
| `OBJECT_DETECTION` | `ObjectExpert` (TFLite/ONNX Edge Detector) | RGB Camera Frame (e.g. 320x320/640x640) | MEDIUM | 25 - 65 ms | Detects vehicles, pedestrians, cyclists, road barriers |
| `SCENE_ANALYSIS` | `SceneExpert` | Camera Frame + Ambient Light | MEDIUM | 20 - 45 ms | Classifies day/night, indoor/outdoor, weather conditions |
| `ROAD_ANALYSIS` | `RoadExpert` | Camera Frame + IMU Pitch/Roll | MEDIUM | 30 - 70 ms | Detects curb, crosswalk, sidewalk boundaries, road surface |
| `TEMPORAL_CHANGE` | `TemporalChangeExpert` | Sliding 3-5 sec temporal buffer | LOW | < 10 ms | Verifies hazard persistence, closing speed, approaching rate |
| `ILLUMINATION_ANALYSIS` | `IlluminationExpert` | Ambient Light sensor + Camera exposure | VERY_LOW | < 2 ms | Evaluates low-light risks, blinding glare, camera fidelity |
| `HAZARD_ANALYSIS` | `HazardExpert` | Fused visual + motion + spatial tokens | LOW | < 15 ms | Synthesizes threat level (collision, trip, sudden vehicle) |
| `SPATIAL_CONTEXT` | `SpatialContextExpert` | GPS + Vector Road/Obstacle Map | LOW | < 10 ms | Evaluates intersection proximity, crosswalk status |
| `EVIDENCE_FUSION` | `EvidenceFusionEngine` | Unfused `List<EvidenceItem>` | LOW | < 8 ms | Correlates multi-modal evidence across time & space |
| `ARBITRATION` | `ArbitrationEngine` | Fused candidate hypotheses | LOW | < 5 ms | Resolves contradictions between vision and kinetic sensors |
| `REASONING` | `LocalReasoningExpert` | Verified evidence graph | LOW | < 20 ms | Produces human-readable, auditable natural language explanations |

---

## 4. Multi-Level Escalation Policy

StreetSense employs a strict 5-stage progressive execution pipeline:

```
[LEVEL 0: SENSOR SANITY & BASELINE]
  Frequency: Continuous (every 20 - 50 ms)
  Check sensor sampling rates, IMU magnitude, ambient lux.
  Filter: If motion is stable and camera has no trigger -> NO ESCALATION.

[LEVEL 1: CHEAP KINETIC & LOCATION SPECIALISTS]
  Trigger: Significant motion delta (acceleration jerk, abrupt stop) or scheduled timer (every 500 ms).
  Execution: MotionExpert + LocationExpert + SensorQualityExpert.
  Output: Kinetic state, user velocity, stationary vs mobile.

[LEVEL 2: ON-DEMAND VISUAL SPECIALISTS]
  Trigger: 
    - MotionExpert detects sudden stop or approaching motion; OR
    - SpatialContext indicates intersection/crosswalk; OR
    - Periodic visual inspection tick (1-2 Hz during active navigation); OR
    - Camera frame brightness change / visual motion detected.
  Execution: ObjectExpert (TFLite/ONNX) + RoadExpert.
  Output: Bounding boxes, classified obstacles, surface edges.

[LEVEL 3: MULTI-MODAL EVIDENCE FUSION & TEMPORAL PERSISTENCE]
  Trigger: Visual obstacle detected or kinetic anomaly confirmed.
  Execution: TemporalChangeExpert + EvidenceFusionEngine.
  Output: Aggregated hypothesis with multi-frame tracking and closing velocity.

[LEVEL 4: CONFLICT ARBITRATION & LOCAL REASONING]
  Trigger: Disagreement between sensors (e.g. Vision detects car moving fast, but GPS/IMU says device is stationary inside a store) or Confidence < 0.70.
  Execution: ArbitrationEngine decides whether to drop, mark UNCERTAIN, or request an additional sensor validation.
  If confirmed, LocalReasoningExpert constructs concise user-facing alert explanation.
```

---

## 5. Confidence Model Architecture

StreetSense explicitly forbids a single, opaque "magic number" confidence score. The system tracks discrete, auditable confidence dimensions:

```kotlin
data class ConfidenceBreakdown(
    val predictionConfidence: Double,      // Raw model output probability
    val inputQualityScore: Double,          // Sensor accuracy, lighting lux, camera blur index
    val temporalConsistencyScore: Double,   // Has this object/event persisted across N frames?
    val sensorReliabilityScore: Double,     // Hardware accuracy status (e.g. GPS ACCURACY_FINE)
    val crossExpertAgreementScore: Double,  // Agreement index between Vision, IMU, and Location
    val geometricConsistencyScore: Double,  // Optical bounding box motion matches IMU velocity
    val finalDecisionConfidence: Double     // Deterministic weighted formula
)
```

### Deterministic Calculation Formula
$$\text{finalConfidence} = w_p C_p \cdot w_q Q_{in} + w_t C_t + w_a C_a + w_g C_g$$
Where weights $w$ sum to 1.0, and any component falling below minimum safety threshold forces an automatic fallback to `UNCERTAIN` or `DEGRADED`.

---

## 6. Conflict Arbitration Engine

When experts return conflicting evidence:
- **Case 1: Visual Phantom**: ObjectExpert detects vehicle with confidence 0.85, but TemporalChangeExpert reports it was present for only 1 frame (< 33ms) and no IMU/Doppler change is observed $\longrightarrow$ Classified as transient visual artifact / reflection; Alert suppressed.
- **Case 2: Kinetic Noise**: Accelerometer detects sudden 3G shock, but Gyroscope and Camera show normal upright landscape $\longrightarrow$ Phone was likely tapped or pocket jostle, not a pedestrian fall.
- **Case 3: Insoluble Contradiction**: Visual expert indicates direct barrier, location expert indicates open authorized walkway, temporal consistency is ambiguous $\longrightarrow$ The ArbitrationEngine outputs `CONFLICT_DETECTED` with severity `WARNING_UNCERTAIN`, lowering alert urgency and prompting user to verify environment visually without triggering panic alarms.

---

## 7. Local Reasoning & Explanation Engine

The Local Reasoning Engine receives an immutable, structured **Evidence Graph**:
- Nodes: Identified entities, kinetic states, geospatial coordinates, timestamps.
- Edges: Spatial proximity, temporal persistence, velocity vectors.

The reasoning output is strictly bound by the evidence:
- **Forbidden**: Making ungrounded assertions ("There is definitely a truck 4.2 meters away" without depth sensor or calibrated bounding box).
- **Required**: Citing the agreeing sources ("Approaching vehicle detected ahead. Optical detection and forward motion agree over 1.8 seconds.").
