import json, os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
COOKIE_PATH = "session/naver_cookies.json"
blog_id = os.environ.get("NAVER_BLOG_ID", "saju_moon")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    with open(COOKIE_PATH, encoding="utf-8") as f:
        context.add_cookies(json.load(f))
    page.goto(f"https://blog.naver.com/{blog_id}/postwrite")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(4000)

    # 도움말 닫기
    btn = page.locator(".se-help-panel-close-button")
    if btn.count() > 0 and btn.first.is_visible():
        btn.first.click()
        page.wait_for_timeout(500)

    # 인용구 스타일 개수 및 data-value 확인
    print("=== 인용구 버튼 목록 ===")
    result = page.evaluate("""() => {
        return Array.from(document.querySelectorAll("[data-name='quotation']")).map(e => ({
            tag: e.tagName,
            dataValue: e.getAttribute('data-value'),
            dataType: e.getAttribute('data-type'),
            cls: String(e.className || '').substring(0, 80),
            visible: e.offsetParent !== null
        }));
    }""")
    for r in result:
        print(f"  <{r['tag']}> data-value={r['dataValue']!r} data-type={r['dataType']!r} visible={r['visible']} cls={r['cls']!r}")

    # 폰트 크기 관련 셀렉터
    print("\n=== 폰트 크기 관련 요소 ===")
    result2 = page.evaluate("""() => {
        const found = [];
        document.querySelectorAll("*").forEach(e => {
            const cls = String(e.className || "");
            const dn = String(e.getAttribute("data-name") || "");
            if ((cls.toLowerCase().includes("font") || cls.toLowerCase().includes("size") ||
                 dn.toLowerCase().includes("font") || dn.toLowerCase().includes("size")) &&
                e.offsetParent !== null) {
                found.push({
                    tag: e.tagName,
                    dn,
                    cls: cls.substring(0, 80),
                    text: (e.innerText || "").trim().substring(0, 20)
                });
            }
        });
        return found.slice(0, 30);
    }""")
    for r in result2:
        print(f"  <{r['tag']}> data-name={r['dn']!r} text={r['text']!r} cls={r['cls']!r}")

    input("\nEnter to close...")
    browser.close()
