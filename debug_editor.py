"""
스마트에디터 ONE 셀렉터 진단 스크립트
실행 후 브라우저에서 직접 확인하세요.
"""
import json
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

COOKIE_PATH = "session/naver_cookies.json"
blog_id = os.environ.get("NAVER_BLOG_ID", "saju_moon")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    context = browser.new_context()
    page = context.new_page()

    # 쿠키 로드
    if os.path.exists(COOKIE_PATH):
        with open(COOKIE_PATH, encoding="utf-8") as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        print("[✓] 쿠키 로드 완료")

    page.goto(f"https://blog.naver.com/{blog_id}/postwrite")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(6000)  # 에디터 완전 초기화 대기

    print("\n=== iframe 목록 ===")
    frames = page.frames
    for i, frame in enumerate(frames):
        print(f"  [{i}] url={frame.url}  name={frame.name}")

    print("\n=== 메인 프레임 셀렉터 탐색 ===")
    for sel in [
        ".se-title-input",
        ".se-content",
        "#titleArea",
        "[placeholder*='제목']",
        ".smarteditor",
        "#se-editor",
        ".se-editor",
    ]:
        count = page.locator(sel).count()
        print(f"  {sel!r:40s} → {count}개")

    print("\n=== 각 iframe 내부 셀렉터 탐색 ===")
    for i, frame in enumerate(frames):
        if frame.url in ("about:blank", ""):
            continue
        print(f"\n  --- iframe[{i}] {frame.url[:80]} ---")
        for sel in [
            # 제목
            ".se-title-input",
            "#titleArea",
            "[placeholder*='제목']",
            "[placeholder*='title']",
            ".se-documentTitle-inputText",
            ".se-title",
            # 본문
            ".se-content",
            "[contenteditable='true']",
            # 툴바
            ".se-toolbar-item-image",
            ".se-toolbar-item-quotation",
            "[data-name='quotation']",
            "[title*='인용']",
            "[aria-label*='인용']",
            # 태그
            ".tag_input",
            "[placeholder*='태그']",
            ".tag-input",
            "#tagInput",
            ".se-tag-input",
            # 발행 버튼
            ".publish_btn",
            "[data-action='publish']",
            ".btn_publish",
            "button:has-text('발행')",
            ".se-publish",
        ]:
            try:
                count = frame.locator(sel).count()
                if count:
                    print(f"    {sel!r:40s} → {count}개  ✓")
            except Exception:
                pass

    # 메인 프레임에서 모든 contenteditable, input, textarea 덤프
    print("\n=== 메인 프레임 contenteditable/input/textarea 전체 ===")
    for sel in ["[contenteditable]", "input", "textarea"]:
        els = page.locator(sel).all()
        for el in els:
            try:
                tag = el.evaluate("e => e.tagName")
                cls = el.get_attribute("class") or ""
                pid = el.get_attribute("id") or ""
                ph = el.get_attribute("placeholder") or ""
                ce = el.get_attribute("contenteditable") or ""
                print(f"  <{tag}> id={pid!r} class={cls[:60]!r} placeholder={ph!r} contenteditable={ce!r}")
            except Exception:
                pass

    # JS로 모든 contenteditable + 제목 관련 요소 탐색
    print("\n=== JS: 모든 contenteditable 요소 ===")
    result = page.evaluate("""() => {
        const els = document.querySelectorAll('[contenteditable]');
        return Array.from(els).map(e => ({
            tag: e.tagName,
            id: e.id,
            className: e.className.substring(0, 80),
            placeholder: e.getAttribute('placeholder') || e.dataset.placeholder || '',
            contenteditable: e.contentEditable,
            text: e.innerText.substring(0, 30),
        }));
    }""")
    for r in result:
        print(f"  <{r['tag']}> id={r['id']!r} class={r['className']!r} placeholder={r['placeholder']!r} text={r['text']!r}")

    # .se-content 내부 HTML 구조 확인
    print("\n=== .se-content 내부 첫 2000자 HTML ===")
    html = page.evaluate("""() => {
        const el = document.querySelector('.se-content');
        return el ? el.innerHTML.substring(0, 2000) : 'NOT FOUND';
    }""")
    print(html)

    # 제목 관련 요소 - string 변환 보장
    print("\n=== JS: 제목/태그/발행 관련 요소 ===")
    result2 = page.evaluate("""() => {
        const keywords = ['title', 'Title', '제목', 'tag', 'Tag', '태그', 'publish', '발행'];
        const found = [];
        document.querySelectorAll('input, button, [contenteditable], textarea').forEach(e => {
            const cls = String(e.className || '');
            const id = String(e.id || '');
            const ph = String(e.getAttribute('placeholder') || '');
            const txt = String(e.innerText || e.textContent || '').trim();
            if (keywords.some(k => cls.includes(k) || id.includes(k) || ph.includes(k) || txt.includes(k))) {
                found.push({
                    tag: e.tagName,
                    id: id.substring(0,50),
                    className: cls.substring(0,80),
                    placeholder: ph.substring(0,50),
                    text: txt.substring(0,30)
                });
            }
        });
        return found.slice(0, 30);
    }""")
    for r in result2:
        print(f"  <{r['tag']}> id={r['id']!r} class={r['className']!r} ph={r['placeholder']!r} text={r['text']!r}")

    # 제목 영역 - .se-canvas 첫 번째 블록 확인
    print("\n=== .se-canvas 직계 자식 블록 목록 ===")
    result3 = page.evaluate("""() => {
        const canvas = document.querySelector('.se-canvas');
        if (!canvas) return ['NOT FOUND'];
        return Array.from(canvas.children).slice(0, 10).map(e => ({
            tag: e.tagName,
            className: String(e.className || '').substring(0, 80),
            id: String(e.id || ''),
            ce: e.contentEditable,
            text: (e.innerText || '').substring(0, 30)
        }));
    }""")
    for r in result3:
        print(f"  <{r['tag']}> ce={r['ce']!r} class={r['className']!r} text={r['text']!r}")

    # 발행 버튼 목록 확인 (visible 한 것만)
    print("\n=== 발행 버튼 상세 ===")
    result4 = page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button'));
        return btns
            .filter(b => (b.innerText||'').includes('발행') || String(b.className||'').includes('publish'))
            .map(b => ({
                text: (b.innerText||'').trim().substring(0,40),
                className: String(b.className||'').substring(0,80),
                visible: b.offsetParent !== null,
                disabled: b.disabled
            }));
    }""")
    for r in result4:
        print(f"  text={r['text']!r} visible={r['visible']} disabled={r['disabled']} class={r['className']!r}")

    # visible한 발행 버튼 클릭
    print("\n=== visible 발행 버튼 클릭 후 태그 입력 탐색 ===")
    visible_publish = page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const btn = btns.find(b => (b.innerText||'').trim() === '발행' && b.offsetParent !== null);
        if (btn) { btn.click(); return btn.className; }
        return null;
    }""")
    print(f"  클릭된 버튼 class: {visible_publish}")
    page.wait_for_timeout(2000)

    result5 = page.evaluate("""() => {
        const found = [];
        document.querySelectorAll('input, textarea, [contenteditable]').forEach(e => {
            const cls = String(e.className || '');
            const ph = String(e.getAttribute('placeholder') || '');
            const id = String(e.id || '');
            found.push({
                tag: e.tagName,
                id: id.substring(0,50),
                className: cls.substring(0,80),
                ph: ph.substring(0,50),
                visible: e.offsetParent !== null
            });
        });
        return found;
    }""")
    print("  클릭 후 모든 input/textarea/contenteditable:")
    for r in result5:
        if r['visible']:
            print(f"  ✓ <{r['tag']}> id={r['id']!r} class={r['className']!r} ph={r['ph']!r}")

    print("\n\n브라우저를 닫으려면 Enter 키를 누르세요...")
    input()
    browser.close()
