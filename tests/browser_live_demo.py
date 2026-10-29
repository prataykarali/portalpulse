"""Fast browser smoke test of the four-page local live demo."""
from pathlib import Path
from playwright.sync_api import sync_playwright

base = 'http://127.0.0.1:8000'
out = Path(__file__).resolve().parents[1] / 'demo_evidence'
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium-browser', headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(base + '/website', wait_until='domcontentloaded')
    page.locator('#connection').get_by_text('BACKEND CONNECTED').wait_for(timeout=30000)
    page.screenshot(path=str(out / '01_command_center.png'), full_page=True)
    page.locator('[data-view-panel="command"] [data-action="start"]').first.click()
    page.wait_for_timeout(3500)
    page.locator('.page-nav [data-view="traffic"]').click()
    page.screenshot(path=str(out / '02_traffic_ramp.png'), full_page=True)
    page.locator('[data-view-panel="traffic"] [data-trigger="result-rush"]').click()
    page.wait_for_timeout(4000)
    page.locator('.page-nav [data-view="intelligence"]').click()
    page.screenshot(path=str(out / '03_model_intelligence.png'), full_page=True)
    page.locator('#neural').screenshot(path=str(out / '04_neural_inspector.png'))
    page.locator('.architecture-frame').screenshot(path=str(out / '05_architecture.png'))
    page.locator('#robot-launch').click()
    assert page.locator('#tour-dialog').is_visible()
    page.locator('#tour-close').click()
    page.locator('.page-nav [data-view="traffic"]').click()
    page.locator('[data-view-panel="traffic"] [data-trigger="database"]').click()
    page.wait_for_timeout(4000)
    page.locator('.page-nav [data-view="guide"]').click()
    page.locator('#test-notifications').click()
    page.locator('#nirantar-warning .nirantar-notice').wait_for(timeout=10000)
    page.screenshot(path=str(out / '06_warning_popup.png'), full_page=True)
    page.locator('#nirantar-warning .nirantar-dismiss').click()
    assert not page.locator('#nirantar-warning .nirantar-notice').count()
    page.locator('.page-nav [data-view="traffic"]').click()
    page.locator('[data-view-panel="traffic"] [data-trigger="recovery"]').click()
    page.wait_for_timeout(4000)
    page.screenshot(path=str(out / '07_recovery.png'), full_page=True)
    page.locator('.page-nav [data-view="guide"]').click()
    page.screenshot(path=str(out / '08_nirantar_bridge.png'), full_page=True)
    with page.expect_popup() as opened:
        page.locator('#open-nirantar').click()
    nirantar_page = opened.value
    assert nirantar_page.url.startswith(page.locator('#open-nirantar').get_attribute('href'))
    nirantar_page.close()
    assert not errors, errors
    print('Browser smoke passed; guided tour, architecture, Nirantar notice, and page errors checked.')
    browser.close()
