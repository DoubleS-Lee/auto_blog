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

    def _add_paragraph_breaks(self, text: str) -> str:
        """마침표 뒤에 줄바꿈 1개 추가 (가독성)."""
        text = re.sub(r'\.(\s+)', '.\n', text)
        text = re.sub(r'\.$', '.\n', text, flags=re.MULTILINE)
        return text

    def _set_font_size(self, page, size: int):
        """폰트 크기 설정: 토글 클릭 → 대기 → fs{size} 옵션 클릭."""
        # 1단계: 드롭다운 토글 버튼 클릭 (data-value 없는 것)
        page.evaluate("""() => {
            const toggle = Array.from(document.querySelectorAll("[data-name='font-size']"))
                .find(e => !e.getAttribute('data-value') && e.offsetParent !== null);
            if (toggle) toggle.click();
        }""")
        page.wait_for_timeout(300)
        # 2단계: 옵션 클릭
        option = page.locator(f"[data-value='fs{size}']")
        if option.count() > 0:
            option.first.click()
        else:
            page.keyboard.press("Escape")
        page.wait_for_timeout(200)

    def _insert_quote5(self, page):
        """인용구5 삽입: 드롭다운 열기 → 5번째(index 4) 스타일 클릭."""
        dropdown = page.locator(".se-document-toolbar-select-option-button")
        if dropdown.count() > 0 and dropdown.first.is_visible():
            dropdown.first.click()
            page.wait_for_timeout(400)
            options = page.locator("[data-name='quotation'][data-value]")
            count = options.count()
            # 인용구5 = index 5, 없으면 마지막
            idx = min(5, count - 1)
            options.nth(idx).click()
            page.wait_for_timeout(400)
        else:
            page.locator("[data-name='quotation']").first.click()
            page.wait_for_timeout(400)

    def _type_with_bold(self, page, text: str):
        """**텍스트** 패턴을 감지하여 굵게 처리하며 입력. 한글 호환을 위해 모두 pyperclip 사용."""
        parts = re.split(r'\*\*(.*?)\*\*', text)
        for idx, part in enumerate(parts):
            if not part:
                continue
            if idx % 2 == 1:  # 굵게
                page.keyboard.press("Control+b")
                pyperclip.copy(part)
                page.keyboard.press("Control+v")
                page.wait_for_timeout(100)
                page.keyboard.press("Control+b")
            else:
                pyperclip.copy(part)
                page.keyboard.press("Control+v")
            page.wait_for_timeout(100)

    def _input_quote_block(self, page, content: str):
        """인용구5 삽입 → 폰트19 설정 → 텍스트 영역 포커스 → 소제목 입력 → 탈출 → 본문 복귀."""
        # 1. 인용구 삽입 (커서는 출처 영역에 놓임)
        self._insert_quote5(page)
        page.wait_for_timeout(500)

        # 2. 폰트 크기 19 먼저 설정 (포커스 이동 무관)
        self._set_font_size(page, 19)

        # 3. 인용구 첫 번째 contenteditable(텍스트 영역) 직접 클릭 → 포커스 확보
        page.evaluate("""() => {
            const components = document.querySelectorAll('.se-component-quotation');
            if (!components.length) return;
            const last = components[components.length - 1];
            const editables = last.querySelectorAll('[contenteditable="true"]');
            // 첫 번째 = 소제목 텍스트 영역, 두 번째 = 출처 입력
            if (editables.length > 0) {
                editables[0].click();
                editables[0].focus();
            }
        }""")
        page.wait_for_timeout(300)

        # 4. 소제목 입력 (pyperclip으로 한글 안전하게)
        pyperclip.copy(content)
        page.keyboard.press("Control+v")
        page.wait_for_timeout(200)

        # 5. 인용구 탈출: 키보드로 블록 바깥으로 이동
        # End → 소제목 줄 끝
        # ArrowDown → 출처 입력 영역
        # ArrowDown → 인용구 바깥 (마지막 블록이면 새 블록 자동 생성)
        # Enter → 새 본문 단락 확보
        page.keyboard.press("End")
        page.wait_for_timeout(100)
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(100)
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(100)
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)

        # 6. 본문 폰트 크기 16 복원
        self._set_font_size(page, 16)
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

    def _close_help_panel(self, page):
        """도움말 패널이 열려 있으면 닫는다."""
        btn = page.locator(".se-help-panel-close-button")
        if btn.count() > 0 and btn.first.is_visible():
            btn.first.click()
            page.wait_for_timeout(500)

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

    def _click_panel_confirm(self, page):
        """도움말 패널 닫고 최종 '✓ 발행' 버튼 클릭 (마지막 visible 발행 버튼)."""
        self._close_help_panel(page)
        page.wait_for_timeout(300)
        page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const candidates = btns.filter(b => {
                const txt = (b.innerText || '').trim();
                return txt.includes('발행') && !txt.includes('예약') && b.offsetParent !== null;
            });
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
            page.locator(".se-components-wrap > :first-child").click()
            page.wait_for_timeout(300)
            page.keyboard.type(title)
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)

            # ── 본문 기본 폰트 크기 16 설정 ──
            self._set_font_size(page, 16)

            # ── 본문 블록 순차 입력 ──
            for block in blocks:
                btype = block.get("type")

                if btype == "text":
                    content = self._add_paragraph_breaks(block.get("content", ""))
                    if "**" in content:
                        self._type_with_bold(page, content)
                    else:
                        pyperclip.copy(content)
                        page.keyboard.press("Control+v")
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(300)

                elif btype == "quote":
                    # 인용구5 고정, 소제목 한 문장, 크기 19
                    self._input_quote_block(page, block.get("content", ""))

                elif btype == "image":
                    raw_path = block.get("path", "").strip()
                    if not raw_path:
                        print("[!] 이미지 경로 없음, 건너뜀")
                        continue
                    image_path = os.path.abspath(raw_path)
                    if not os.path.isfile(image_path):
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
                page.keyboard.type(tag)
                page.keyboard.press("Enter")
                page.wait_for_timeout(200)

            # ── 최종 발행 (패널 안 '✓ 발행' 버튼) ──
            self._click_panel_confirm(page)
            page.wait_for_timeout(3000)

            browser.close()

        return f"게시 완료: {title}"
