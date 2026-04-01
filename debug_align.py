"""스마트에디터 ONE 정렬 버튼 DOM 확인용 디버그 스크립트"""
import os, json
from dotenv import load_dotenv
load_dotenv()

COOKIE_PATH = "session/naver_cookies.json"
blog_id = os.environ.get("NAVER_BLOG_ID")

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    with open(COOKIE_PATH, encoding="utf-8") as f:
        cookies = json.load(f)
    context.add_cookies(cookies)

    page.goto(f"https://blog.naver.com/{blog_id}/postwrite")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    # 도움말 닫기
    btn = page.locator(".se-help-panel-close-button")
    if btn.count() > 0 and btn.first.is_visible():
        btn.first.click()
        page.wait_for_timeout(500)

    # 정렬 관련 버튼 탐색
    result = page.evaluate("""() => {
        const candidates = [];

        // data-name에 align 포함된 요소
        document.querySelectorAll('[data-name]').forEach(el => {
            const name = el.getAttribute('data-name') || '';
            if (name.includes('align') || name.includes('justify')) {
                candidates.push({
                    tag: el.tagName,
                    dataName: name,
                    dataValue: el.getAttribute('data-value'),
                    class: el.className,
                    visible: el.offsetParent !== null,
                    text: (el.innerText || '').trim().slice(0, 30),
                });
            }
        });

        // title/aria-label에 align/정렬 포함된 버튼
        document.querySelectorAll('button, [role="button"]').forEach(el => {
            const title = (el.getAttribute('title') || el.getAttribute('aria-label') || '').toLowerCase();
            if (title.includes('align') || title.includes('정렬') || title.includes('center') || title.includes('가운데')) {
                candidates.push({
                    tag: el.tagName,
                    dataName: el.getAttribute('data-name'),
                    dataValue: el.getAttribute('data-value'),
                    class: el.className,
                    visible: el.offsetParent !== null,
                    title: title,
                });
            }
        });

        return candidates;
    }""")

    print(f"\n정렬 관련 요소 {len(result)}개:")
    for item in result:
        print(item)

    # 드롭다운 열기
    print("\n정렬 드롭다운 클릭 중...")
    page.evaluate("""() => {
        const btn = document.querySelector('[data-name="align-drop-down-with-justify"]');
        if (btn) btn.click();
    }""")
    page.wait_for_timeout(500)

    # 열린 후 옵션 탐색
    options = page.evaluate("""() => {
        const items = [];
        document.querySelectorAll('[data-name], [data-value]').forEach(el => {
            const name = el.getAttribute('data-name') || '';
            const val = el.getAttribute('data-value') || '';
            if ((name.includes('align') || val.includes('align') || val.includes('center') || val.includes('left') || val.includes('right'))
                && el.offsetParent !== null) {
                items.push({
                    tag: el.tagName,
                    dataName: name,
                    dataValue: val,
                    class: el.className.slice(0, 60),
                });
            }
        });
        return items;
    }""")
    print(f"\n드롭다운 옵션 {len(options)}개:")
    for o in options:
        print(o)

    input("\n확인 후 Enter...")
    browser.close()
