"""Record one complete automatic local result-day scenario with Playwright."""
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parents[1] / 'demo_evidence'
out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium-browser', headless=True, args=['--no-sandbox'])
    context = browser.new_context(viewport={'width': 1440, 'height': 900}, record_video_dir=str(out), record_video_size={'width': 1440, 'height': 900})
    page = context.new_page()
    page.goto('http://127.0.0.1:8000/live-demo', wait_until='domcontentloaded')
    page.locator('#connection').get_by_text('BACKEND CONNECTED').wait_for(timeout=30000)
    page.locator('[data-view-panel="command"] [data-action=start]').first.click()
    page.wait_for_function("() => document.querySelector('#phase')?.textContent === 'BASELINE' && document.querySelector('#status')?.textContent.includes('Generating portal requests')", timeout=30000, polling=200)
    page.wait_for_function("() => document.querySelector('#comparison')?.textContent.includes('EXECUTED') && document.querySelector('#recovery-state')?.textContent.includes('RECOVERY_VERIFIED')", timeout=130000, polling=300)
    page.locator('.page-nav [data-view="traffic"]').click()
    page.screenshot(path=str(out/'07_recovery.png'), full_page=True)
    page.locator('.page-nav [data-view="intelligence"]').click()
    page.locator('.architecture-frame').screenshot(path=str(out/'05_architecture.png'))
    page.wait_for_function("() => document.querySelector('#phase')?.textContent === 'NORMAL' && document.querySelector('#status')?.textContent.includes('Traffic stopped')", timeout=240000, polling=1000)
    history = page.request.get('http://127.0.0.1:8000/api/v1/control-loop/history?limit=100').json()
    assert any(c['actuation_status']=='EXECUTED' and c['verification_status']=='RECOVERY_VERIFIED' for c in history), 'No verified M7 actuation in run'
    page.locator('.page-nav [data-view="command"]').click()
    page.screenshot(path=str(out/'09_complete_run.png'), full_page=True)
    video = page.video
    context.close()
    video_path = Path(video.path())
    video_path.replace(out/'complete_result_day.webm')
    browser.close()
    print('Recorded complete run to', out/'complete_result_day.webm')
