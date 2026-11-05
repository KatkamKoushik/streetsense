import os
import time
import pytest

playwright = pytest.importorskip("playwright")

web_dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web-console", "dist"))
if not os.path.isdir(web_dist_dir) or not os.path.exists(os.path.join(web_dist_dir, "index.html")):
    pytest.skip("web-console dist bundle not built; skipping Playwright E2E browser tests", allow_module_level=True)

from playwright.async_api import async_playwright
from app.db.session import AsyncSessionLocal
from app.db.repositories import EventRepository
from app.schemas.events import DetectedEvent, EventCategory, EventSeverity, ConfidenceBreakdown


@pytest.mark.asyncio
async def test_playwright_console_loads_and_renders_layout(live_server):
    """
    Playwright E2E: Verifies full DOM structure, panels, and CSS styling in headless Chromium.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        await page.goto(live_server["http_url"])
        await page.wait_for_selector("header", timeout=5000)

        # 1. Page Title & Brand Header
        title = await page.title()
        assert title == "StreetSense — Real-Time Observation Console"

        header_text = await page.text_content("header")
        assert "StreetSense" in header_text
        assert "WEB CONSOLE" in header_text

        # 2. Five Core Real-Time Diagnostic Panels
        content = await page.content()
        assert "Edge Hardware State" in content
        assert "Real-Time IMU Telemetry" in content
        assert "Geospatial Tracking" in content
        assert "Hazard" in content and "Incident" in content
        assert "Selective Expert Waterfall" in content

        # 3. Verify zero unhandled browser console errors
        critical_errors = [e for e in console_errors if "favicon" not in e]
        assert len(critical_errors) == 0, f"Unexpected browser errors: {critical_errors}"

        await browser.close()


@pytest.mark.asyncio
async def test_playwright_console_websocket_realtime_connection(live_server):
    """
    Playwright E2E: Verifies browser token acquisition, WebSocket first-frame auth, and live status indicator.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(live_server["http_url"])
        # Wait for WebSocket client to authenticate and badge to switch to CONNECTED
        await page.wait_for_selector("[data-testid='connection-badge'] span:has-text('CONNECTED')", timeout=5000)

        badge_text = await page.text_content("[data-testid='connection-badge']")
        assert "CONNECTED" in badge_text
        assert "ms)" in badge_text

        await browser.close()


@pytest.mark.asyncio
async def test_playwright_console_event_rendering_and_dismissal(live_server):
    """
    Playwright E2E: Verifies active incident rendering in feed and interactive dismissal.
    """
    # 1. Seed a unique test event in the database
    now_ns = time.time_ns()
    event_id = f"evt_pw_{now_ns}"
    event = DetectedEvent(
        event_id=event_id,
        session_id="session_playwright_test",
        timestamp_ns=now_ns,
        category=EventCategory.PEDESTRIAN_FALL_OR_IMPACT,
        severity=EventSeverity.CRITICAL,
        confidence_breakdown=ConfidenceBreakdown(
            prediction_confidence=0.95,
            input_quality=0.90,
            temporal_consistency=0.91,
            sensor_reliability=0.88,
            cross_expert_agreement=0.92,
            geometric_consistency=0.89,
            evidence_quality=0.93,
            final_decision_confidence=0.91
        ),
        contributing_evidence_ids=[],
        explanation=f"Playwright E2E unique alert {event_id}",
        haptic_pattern="RAPID_DOUBLE_PULSE",
        latitude=37.7749,
        longitude=-122.4194,
        is_dismissed=False
    )

    async with AsyncSessionLocal() as db_session:
        repo = EventRepository(db_session)
        await repo.save_event(event)

    # 2. Open console and verify event rendered in feed
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(live_server["http_url"])
        await page.wait_for_selector(f"text={event_id}", timeout=5000)

        content = await page.content()
        assert "CRITICAL" in content
        assert event_id in content

        # 3. Locate the card containing this unique event and click its Dismiss button
        dismiss_btn = page.locator(f"[data-testid='dismiss-{event_id}']")
        await dismiss_btn.click()

        # 4. Verify the unique event disappears from the feed
        await page.wait_for_selector(f"text={event_id}", state="detached", timeout=5000)
        dismissed_content = await page.content()
        assert event_id not in dismissed_content

        await browser.close()


@pytest.mark.asyncio
async def test_playwright_console_security_invalid_key_warning(live_server):
    """
    Playwright E2E: Verifies fail-closed security warning banner when console API key is rejected.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Inject invalid API key into localStorage
        await page.goto(live_server["http_url"])
        await page.evaluate("() => localStorage.setItem('streetsense_console_key', 'unauthorized_hacker_key_999')")
        await page.reload()

        # Verify security warning banner is rendered
        await page.wait_for_selector("text=Security Warning:", timeout=5000)
        banner_text = await page.text_content("text=Security Warning:")
        assert "Security Warning:" in banner_text

        # Verify header remains DISCONNECTED
        await page.wait_for_selector("text=DISCONNECTED", timeout=5000)
        badge_text = await page.text_content("[data-testid='connection-badge']")
        assert "DISCONNECTED" in badge_text

        # Restore valid key
        await page.evaluate("() => localStorage.removeItem('streetsense_console_key')")
        await browser.close()


@pytest.mark.asyncio
async def test_playwright_console_responsive_mobile_viewport(live_server):
    """
    Playwright E2E: Emulates mobile device viewport (375x812) and checks responsive layout.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # iPhone 13 mini viewport emulation
        page = await browser.new_page(viewport={"width": 375, "height": 812}, is_mobile=True)

        await page.goto(live_server["http_url"])
        await page.wait_for_selector("header", timeout=5000)

        title = await page.title()
        assert title == "StreetSense — Real-Time Observation Console"

        # Verify layout renders without JS crashes on mobile viewport
        content = await page.content()
        assert "StreetSense" in content
        assert "Edge Hardware State" in content

        await browser.close()
