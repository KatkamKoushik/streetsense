# Accessibility Statement for StreetSense

StreetSense is committed to ensuring digital accessibility for people of all abilities, including individuals with disabilities. As a pedestrian safety and hazard detection platform, accessibility is fundamental to our mission of protecting pedestrians through timely, clear, and multi-modal sensory feedback.

---

## Accessibility Standards & Conformance

We aim to adhere to the following accessibility standards and guidelines across our software components:

- **Web Content Accessibility Guidelines (WCAG) 2.1 Level AA**: For the Web Observation Console.
- **Section 508 Standards**: Ensuring government and public sector accessibility compliance.
- **Android Accessibility Guidelines**: Following Google Android's best practices for touch targets, contrast ratios, and screen reader integration.

---

## Accessibility Features by Subsystem

### 1. Android Mobile Edge Client

- **Multi-Modal Alert Feedback**: Life-safety hazard alerts produce both visual cues and distinct haptic vibration patterns (such as `STRONG_DOUBLE_PULSE`), ensuring alerts are perceivable by users who are deaf, hard of hearing, blind, or visually impaired.
- **Screen Reader Support**: All interactive UI elements, sensor health cards, and alert banners in the Jetpack Compose HUD include descriptive `contentDescription` attributes compatible with **TalkBack**.
- **Dynamic Type & Font Scaling**: UI text supports system-level text magnification and dynamic font resizing without layout clipping or text overlap.
- **Minimum Touch Targets**: All interactive buttons and toggles maintain minimum touch target dimensions of 48dp x 48dp.
- **High Contrast Theme**: Dark-mode UI with high-contrast foreground text against dark backgrounds to minimize glare and maximize readability in outdoor daylight conditions.

### 2. Web Observation Console

- **Keyboard Navigation**: Complete keyboard navigability across all cards, feeds, maps, and interactive controls without requiring a mouse.
- **Visible Focus Indicators**: High-contrast, visible focus rings on all active elements.
- **ARIA Landmarks & Roles**: Semantic HTML landmarks (`<header>`, `<main>`, `<section>`) and ARIA roles for screen reader orientation.
- **Live Regions for Dynamic Ingress**: WebSocket-driven hazard alerts utilize `aria-live="polite"` regions so assistive technologies announce new alerts without interrupting ongoing speech.
- **Accessible Color Contrast**: UI color palette complies with WCAG AA minimum contrast ratio (4.5:1 for normal text, 3:1 for large text). Critical alerts use icon shapes and text labels in addition to color coding to prevent colorblindness exclusion.
- **Canvas Chart Text Alternatives**: Live HTML5 Canvas IMU charts provide structured tabular and text-based summaries of telemetry values for assistive technologies.

---

## Supported Environments

The accessible interfaces are tested and supported in the following environments:

- **Mobile**: Android 12 through Android 16 with Google TalkBack enabled.
- **Web Browsers**: Current versions of Google Chrome, Mozilla Firefox, Microsoft Edge, and Apple Safari.
- **Screen Readers**: NVDA and JAWS on Windows, VoiceOver on macOS and iOS, TalkBack on Android.

---

## Known Limitations & Planned Improvements

While we strive for comprehensive accessibility, some areas are actively being enhanced:

- **Spatial Hazard Map**: Interactive map pins currently provide text coordinates; a richer tabular alternative for all active geofenced incidents is under development.
- **Customizable Vibration Patterns**: We plan to allow users to customize haptic feedback duration and intensity profiles based on personal tactile sensitivity.

---

## Feedback & Reporting Accessibility Barriers

We welcome your feedback on the accessibility of StreetSense. If you encounter accessibility barriers, experience difficulty accessing any part of our platform, or have suggestions for improvement, please let us know:

- **Email**: [koushikkatkam@gmail.com](mailto:koushikkatkam@gmail.com)
- **Subject**: `[ACCESSIBILITY ISSUE] StreetSense - <Description>`
- **Response Commitment**: We aim to acknowledge accessibility reports within 3 business days and provide a remediation timeline or workaround within 7 business days.

