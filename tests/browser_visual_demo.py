"""Long browser verification and recording for the illustrated live demo UI."""
from pathlib import Path
import shutil
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
OUT = Path(__file__).resolve().parents[1] / 'demo_evidence' / 'ui_redesign'
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium-browser', headless=True, args=['--no-sandbox'])
    context = browser.new_context(viewport={'width': 1440, 'height': 900}, record_video_dir=str(OUT), record_video_size={'width': 1440, 'height': 900})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE + '/website', wait_until='domcontentloaded')
    page.locator('#connection').get_by_text('BACKEND CONNECTED').wait_for(timeout=30000)
    page.locator('.page-nav [data-view="traffic"]').click()
    page.locator('[data-action="reset"]').click()
    page.locator('.page-nav [data-view="command"]').click()
    started_ms = time.time() * 1000
    page.locator('[data-view-panel="command"] [data-action="start"]').first.click()
    observed = []
    unique_rps = set()
    unique_p95 = set()
    captured = set()
    deadline = time.monotonic() + 235
    while time.monotonic() < deadline:
        snapshot = page.evaluate("async () => (await fetch('/api/v1/live-demo/snapshot')).json()")
        phase = snapshot['traffic']['phase']
        if phase not in observed:
            observed.append(phase)
            print('phase', phase, 'rps', snapshot['traffic']['real_requests_per_sec'], 'p95', snapshot['traffic']['p95'], flush=True)
        unique_rps.add(round(snapshot['traffic']['real_requests_per_sec'], 1))
        unique_p95.add(round(snapshot['traffic']['p95'], 1))
        if phase == 'RAMP' and 'traffic' not in captured:
            page.locator('.page-nav [data-view="traffic"]').click()
            page.screenshot(path=str(OUT / 'live_traffic.png'), full_page=True)
            captured.add('traffic')
        elif phase == 'ANOMALY_DETECTION' and 'intelligence' not in captured:
            page.locator('.page-nav [data-view="intelligence"]').click()
            page.screenshot(path=str(OUT / 'live_intelligence.png'), full_page=True)
            page.locator('#replay-cycle').click()
            page.wait_for_timeout(1100)
            page.locator('#robot-launch').click()
            assert page.locator('#tour-dialog').is_visible()
            page.screenshot(path=str(OUT / 'guided_tour.png'))
            page.locator('#tour-close').click()
            captured.add('intelligence')
        elif phase == 'POLICY_ACTION' and 'policy' not in captured:
            page.locator('.page-nav [data-view="intelligence"]').click()
            page.screenshot(path=str(OUT / 'live_decision.png'), full_page=True)
            captured.add('policy')
        elif phase == 'CONTROLLED_RECOVERY' and 'response' not in captured:
            page.locator('.page-nav [data-view="traffic"]').click()
            page.screenshot(path=str(OUT / 'live_recovery.png'), full_page=True)
            captured.add('response')
        if phase == 'NORMAL' and not snapshot['traffic']['is_running']:
            break
        page.wait_for_timeout(3000)
    else:
        raise AssertionError('The complete scenario did not reach NORMAL in 235 seconds')
    page.locator('.page-nav [data-view="traffic"]').click()
    page.wait_for_timeout(800)
    page.screenshot(path=str(OUT / 'verified_recovery.png'), full_page=True)
    page.locator('.page-nav [data-view="guide"]').click()
    page.screenshot(path=str(OUT / 'nirantar_overlay.png'), full_page=True)
    page.locator('.page-nav [data-view="guide"]').click()
    page.screenshot(path=str(OUT / 'feature_guide.png'), full_page=True)
    history = page.evaluate("async () => (await fetch('/api/v1/control-loop/history?limit=100')).json()")
    history = [x for x in history if datetime.fromisoformat(x['timestamp']).timestamp() * 1000 >= started_ms]
    executed = [x for x in history if x.get('actuation_status') == 'EXECUTED']
    verified = [x for x in history if x.get('verification_status') == 'RECOVERY_VERIFIED']
    assert len(observed) >= 7, observed
    assert len(unique_rps) >= 6, unique_rps
    assert len(unique_p95) >= 6, unique_p95
    assert all(phase in observed for phase in ['BASELINE', 'RAMP', 'RESULT_RUSH', 'SATURATION', 'POLICY_ACTION', 'CONTROLLED_RECOVERY', 'NORMAL']), observed
    assert executed, 'No M7 action executed in this run'
    assert verified, 'No post-action recovery verified in this run'
    assert not errors, errors
    print('observed', observed, flush=True)
    print('unique rps', len(unique_rps), 'unique p95', len(unique_p95), 'executed', len(executed), 'verified', len(verified), 'browser errors', errors, flush=True)
    video_path = page.video.path()
    context.close()
    shutil.copy2(video_path, OUT / 'complete_visual_demo.webm')
    browser.close()
