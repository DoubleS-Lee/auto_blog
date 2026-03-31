import os
import re
import json
import pyperclip
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

COOKIE_PATH = "session/naver_cookies.json"


class SmartEditorInput(BaseModel):
    title: str = Field(..., description="블로그 글 제목")
    blocks: list = Field(
        ...,
        description=(
            "[{'type':'text','content':'...'}, "
            "{'type':'quote','content':'소제목'}, "
            "{'type':'image','path':'...'}] 형태의 블록 배열"
        )
    )
    tags: str = Field(..., description="태그 목록 (쉼표 구분, 최대 30개)")


class NaverSmartEditorTool(BaseTool):
    name: str = "naver_smart_editor_publish"
    description: str = "Playwright로 블록 배열을 순서대로 스마트에디터 ONE에 입력하고 발행한다."
    args_schema: type = SmartEditorInput

    def _type_with_bold(self, page, text: str):
        """**텍스트** 패턴을 감지하여 굵게 처리하며 입력."""
        parts = re.split(r'\*\*(.*?)\*\*', text)
        for idx, part in enumerate(parts):
            if not part:
                continue
            if idx % 2 == 1:  # 굵게
                page.keyboard.press("Control+b")
                page.keyboard.type(part)
                page.keyboard.press("Control+b")
            else:
                pyperclip.copy(part)
                page.keyboard.press("Control+v")

    def _input_quote_block(self, page, content: str):
        """인용구 블록 입력: [data-name='quotation'] 첫 번째 항목 클릭."""
        page.locator("[data-name='quotation']").first.click()
        page.wait_for_timeout(400)
        page.keyboard.type(content)
        # 인용구 블록 탈출
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)

    def _load_or_login(self, page, context):
        if os.path.exists(COOKIE_PATH):
            with open(COOKIE_PATH, encoding="utf-8") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            page.goto("https://www.naver.com")
            page.wait_for_timeout(1000)
        else:
            page.goto("https://nid.naver.com/nidlogin.login")
            print("\n[!] 네이버 로그인 후 Enter 키를 누르세요...")
            input()
            cookies = context.cookies()
            os.makedirs("session", exist_ok=True)
            with open(COOKIE_PATH, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print("[✓] 쿠키 저장 완료")

    def _click_publish_button(self, page):
        """상단 '발행' 버튼 클릭 → 패널 열기."""
        page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const btn = btns.find(b => {
                const txt = (b.innerText || '').trim();
                return txt === '발행' && b.offsetParent !== null;
            });
            if (btn) btn.click();
        }""")

    def _close_help_panel(self, page):
        """도움말 패널이 열려 있으면 닫는다."""
        btn = page.locator(".se-help-panel-close-button")
        if btn.count() > 0 and btn.first.is_visible():
            btn.first.click()
            page.wait_for_timeout(500)

    def _click_panel_confirm(self, page):
        """도움말 패널 닫고 최종 '✓ 발행' 버튼 클릭.
        상단 '발행'(패널 열기)과 구분하기 위해 마지막 visible 발행 버튼을 클릭."""
        self._close_help_panel(page)
        page.wait_for_timeout(300)
        page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const candidates = btns.filter(b => {
                const txt = (b.innerText || '').trim();
                return txt.includes('발행') && !txt.includes('예약') && b.offsetParent !== null;
            });
            // 마지막 발행 버튼이 패널 확인 버튼
            if (candidates.length > 0) candidates[candidates.length - 1].click();
        }""")

    def _run(self, title: str, blocks: list, tags: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return "오류: playwright가 설치되지 않았습니다. pip install playwright && playwright install chromium"

        blog_id = os.environ.get("NAVER_BLOG_ID")
        if not blog_id:
            return "오류: NAVER_BLOG_ID 환경변수가 없습니다."

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            self._load_or_login(page, context)

            page.goto(f"https://blog.naver.com/{blog_id}/postwrite")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # ── 도움말 패널 닫기 (가장 먼저) ──
            self._close_help_panel(page)

            # ── 제목 입력 ──
            # .se-components-wrap 첫 번째 블록이 제목 영역
            page.locator(".se-components-wrap > :first-child").click()
            page.wait_for_timeout(300)
            page.keyboard.type(title)
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)

            # ── 본문 블록 순차 입력 ──
            for block in blocks:
                btype = block.get("type")

                if btype == "text":
                    content = block.get("content", "")
                    if "**" in content:
                        self._type_with_bold(page, content)
                    else:
                        pyperclip.copy(content)
                        page.keyboard.press("Control+v")
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(300)

                elif btype == "quote":
                    self._input_quote_block(page, block.get("content", ""))

                elif btype == "image":
                    image_path = os.path.abspath(block.get("path", ""))
                    if not os.path.exists(image_path):
                        print(f"[!] 이미지 파일 없음, 건너뜀: {image_path}")
                        continue
                    with page.expect_file_chooser() as fc_info:
                        page.locator(".se-toolbar-item-image").click()
                    fc_info.value.set_files(image_path)
                    page.wait_for_timeout(3000)
                    page.keyboard.press("ArrowDown")
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(300)

            # ── 발행 패널 열기 ──
            self._click_publish_button(page)
            page.wait_for_timeout(2000)

            # ── 태그 입력 (#tag-input, 최대 30개) ──
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            tag_input = page.locator("#tag-input")
            for tag in tag_list[:30]:
                tag_input.click()
                page.keyboard.type(tag)   # fill() 대신 type()으로 직접 입력
                page.keyboard.press("Enter")
                page.wait_for_timeout(200)

            # ── 최종 발행 (패널 안 '✓ 발행' 버튼) ──
            self._click_panel_confirm(page)
            page.wait_for_timeout(3000)

            browser.close()

        return f"게시 완료: {title}"
