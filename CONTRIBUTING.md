# Contributing to StreetSense

Thank you for your interest in contributing to **StreetSense**! We welcome contributions from developers, researchers, and designers committed to building transparent, edge-first mobile sensing systems.

---

## Code of Conduct

All contributors and maintainers are expected to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating in project discussions or submitting code.

---

## Architectural Philosophy & Strict Standards

Before contributing code, please keep in mind the core principles of StreetSense:

1. **Selective Multi-Expert Routing**: Do not introduce heavy, always-on inference loops. Cheap deterministic checks run continuously; expensive AI models run only when justified by kinetic anomalies or sensor ambiguity.
2. **Zero-Mock Policy**: We enforce an uncompromising zero-mock policy across all layers:
   - No fabricated telemetry, dummy sine waves, or hardcoded coordinates.
   - If an edge model or hardware sensor is unavailable, return typed `ExecutionStatus.UNAVAILABLE` with setup prerequisites rather than generating synthetic results.
   - Confidence scores must derive from mathematical evidence fusion formulas, never random number generators.
3. **Offline-First Resilience**: Immediate life-safety alerts must be evaluated and triggered locally on-device. Network sync to the backend must be asynchronous, buffered, and idempotent.

---

## Getting Started

### Prerequisites
- **Python**: 3.12+ (Backend & test suites)
- **Node.js**: 20+ and `npm` (Web Console)
- **Android Studio**: Ladybug / Koala with Android SDK Platform 34 and JDK 17
- **Git**

### Repository Setup
1. Fork and clone the repository:
   ```bash
   git clone https://github.com/KatkamKoushik/streetsense.git
   cd streetsense
   ```

2. Backend setup:
   ```bash
   cd backend
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   pip install -r requirements.txt
   pytest -v
   cd ..
   ```

3. Web Console setup:
   ```bash
   cd web-console
   npm install
   npm run build
   cd ..
   ```

4. Android client setup:
   - Open Android Studio and open the `android/` directory.
   - Allow Gradle sync to complete (Gradle 8.7, AGP 8.5).
   - Run unit tests: `./gradlew test` (or run via Android Studio).

---

## Development Workflow

### Branching Strategy
- Branch from `main`.
- Name your branch descriptively:
  - `feature/<short-description>` (for new capabilities or sensors)
  - `fix/<issue-number>-<short-description>` (for bug fixes)
  - `docs/<short-description>` (for documentation updates)

### Commit Message Guidelines
We follow Conventional Commits conventions:
```
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
```
- **Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`
- **Scope**: `android`, `backend`, `web-console`, `engine`, `protocol`, `docs`
- **Examples**:
  - `feat(engine): add temporal window jerk variance heuristic`
  - `fix(web-console): correct canvas devicePixelRatio scaling on high-DPI displays`
  - `docs(readme): update deployment instructions for local transport`

---

## Testing Requirements

Every pull request that modifies code must include automated tests:

1. **Backend Changes**:
   - Write unit and integration tests in `backend/tests/`.
   - Ensure all tests pass: `cd backend && pytest -v`.
2. **Android Changes**:
   - Write JUnit tests in `android/app/src/test/`.
   - Ensure tests pass with `./gradlew test`.
3. **Web Console Changes**:
   - Ensure clean compilation: `cd web-console && npm run build`.

---

## Pull Request Process

1. Ensure your local branch is rebased on top of the latest `main`.
2. Verify that all automated tests pass across backend, android, and web-console.
3. Fill out the provided [Pull Request Template](.github/pull_request_template.md) completely.
4. Maintainers will review your PR against:
   - Zero-Mock compliance
   - Performance and latency implications
   - Test coverage and code clarity
   - Accessibility and documentation updates

---

## Reporting Issues & Requesting Features

- **Bug Reports**: Open an issue using the [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md). Include device hardware details, Android API level, steps to reproduce, and relevant logs.
- **Feature Requests**: Open an issue using the [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md). Detail the proposed sensor/capability, resource consumption profile, and evidence fusion criteria.

---

## Questions and Support

For questions, open a discussion in GitHub Discussions or contact the maintainers at [koushikkatkam@gmail.com](mailto:koushikkatkam@gmail.com).

