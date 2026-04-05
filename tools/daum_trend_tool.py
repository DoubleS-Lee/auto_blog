import re
from datetime import datetime
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class DaumTrendInput(BaseModel):
    max_keywords: int = Field(default=20, description="가져올 최대 트렌드 키워드 수")


class DaumTrendTool(BaseTool):
    name: str = "daum_realtime_trend"
    description: str = (
        "다음(Daum) 포털에서 실시간 트렌드 키워드를 가져온다. "
        "Playwright로 JavaScript 렌더링 후 ol.list_trendrank 에서 키워드를 추출한다."
    )
    args_schema: type = DaumTrendInput

    def _run(self, max_keywords: int = 20) -> str:
        today = datetime.today().strftime("%Y-%m-%d %H:%M")

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto("https://www.daum.net/", wait_until="domcontentloaded", timeout=20000)

                # ol.list_trendrank 가 나타날 때까지 대기 (최대 10초)
                try:
                    page.wait_for_selector("ol.list_trendrank", timeout=10000)
                except Exception:
                    pass  # 없어도 계속 시도

                # data-tiara-copy 속성으로 키워드 추출
                elements = page.query_selector_all("ol.list_trendrank a.link_trendrank")
                keywords = []
                for el in elements:
                    kw = el.get_attribute("data-tiara-copy") or ""
                    kw = kw.strip()
                    if kw:
                        keywords.append(kw)

                # fallback: tit_item 텍스트
                if not keywords:
                    elements = page.query_selector_all("ol.list_trendrank strong.tit_item")
                    for el in elements:
                        kw = (el.text_content() or "").strip()
                        if kw:
                            keywords.append(kw)

                browser.close()

        except Exception as e:
            return (
                f"[다음 실시간 트렌드 — {today}]\n"
                f"⚠ 오류 발생: {e}\n"
                "KEYWORD_LIST: "
            )

        if not keywords:
            return (
                f"[다음 실시간 트렌드 — {today}]\n"
                "⚠ 키워드를 가져오지 못했습니다. 다음 페이지 구조가 변경되었을 수 있습니다.\n"
                "KEYWORD_LIST: "
            )

        # 중복 제거 (순서 보존)
        seen: set = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        unique = unique[:max_keywords]

        lines = [f"[다음 실시간 트렌드 — {today}]"]
        for rank, kw in enumerate(unique, 1):
            lines.append(f"{rank}위 | {kw}")

        lines.append(f"\nKEYWORD_LIST: {' | '.join(unique)}")
        return "\n".join(lines)
