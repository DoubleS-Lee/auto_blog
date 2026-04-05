import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("페이지 로딩 중...")
        await page.goto("https://blackkiwi.net/service/trend", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        print("로딩 완료")

        # popularKeywordList 존재 여부
        el = await page.query_selector("#popularKeywordList")
        print(f"#popularKeywordList 존재: {el is not None}")

        # 전체 ID 목록
        ids = await page.evaluate("() => Array.from(document.querySelectorAll('[id]')).map(e => e.id)")
        print(f"페이지 ID 목록: {ids}")

        # keyword 포함 링크
        links = await page.evaluate("""
            () => Array.from(document.querySelectorAll('a'))
                .filter(a => (a.href||'').includes('keyword'))
                .slice(0,5)
                .map(a => a.href + ' | ' + a.innerText.trim())
        """)
        print(f"keyword 링크: {links}")

        # popularKeywordList 자식 수
        count = await page.evaluate("""
            () => {
                const el = document.getElementById('popularKeywordList');
                return el ? el.children.length : -1;
            }
        """)
        print(f"popularKeywordList 자식 수: {count}")

        # 페이지 HTML 저장
        html = await page.content()
        with open("_debug_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("HTML 저장 완료: _debug_page.html")

        await browser.close()

asyncio.run(main())
