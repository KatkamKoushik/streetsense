# Security Policy

## Supported Versions

StreetSense maintains security patches for the following versions:

| Version | Supported          |
| :---    | :---:              |
| 1.0.x   | Yes                |
| < 1.0   | No                 |

---

## Reporting a Vulnerability

The StreetSense engineering team takes the security of our mobile sensing edge and backend gateway infrastructure seriously.

If you discover a security vulnerability, **please do not disclose it publicly or open a public GitHub issue.** Instead, please report it directly through coordinated disclosure:

1. **Email**: Send a detailed report to [koushikkatkam@gmail.com](mailto:koushikkatkam@gmail.com).
2. **Subject Line**: `[SECURITY VULNERABILITY] StreetSense - <Brief Description>`
3. **Report Details**:
   - Component affected (Android edge client, FastAPI gateway, WebSocket transport, Web Console)
   - Detailed description of the potential vulnerability
   - Step-by-step reproduction instructions or proof-of-concept
   - Impact assessment (e.g., privilege escalation, replay attack, denial of service)

### Response SLA
- **Initial Acknowledgment**: Within 48 hours of receipt.
- **Status Updates**: Periodic updates regarding triaging and progress towards remediation.
- **Remediation**: Once verified, patches will be authored, tested, and published with credit to the reporter (unless anonymity is requested).

---

## Security Model Overview

1. **Authentication**: Cryptographic JWT access tokens and device bearer credentials with configurable expiration.
2. **WebSocket Protection**: Sequence-numbered envelopes with monotonic replay protection and automatic deduplication by `message_id`.
3. **Data Isolation**: On-device sensor ring buffers are held exclusively in volatile memory; only fused incident events and diagnostic summaries are persisted.
4. **Transport**: TLS 1.3 encryption for production HTTPS/WSS deployments.

For the comprehensive system threat model, cryptographic token lifecycle, and attack tree analysis, please refer to [docs/SECURITY.md](docs/SECURITY.md).

