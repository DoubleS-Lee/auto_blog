import asyncio
import json
from urllib.parse import unquote
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class BlackKiwiTrendInput(BaseModel):
    top_n: int = Field(default=30, description="가져올 트렌드 키워드 수 (기본 30)")


class BlackKiwiTrendTool(BaseTool):
    name: str = "blackkiwi_trend"
    description: str = (
        "블랙키위(blackkiwi.net)의 실시간 인기 트렌드 키워드를 수집한다. "
        "트래픽 순으로 정렬된 키워드와 트래픽량을 반환한다."
    )
    args_schema: type = BlackKiwiTrendInput

    def _run(self, top_n: int = 30) -> str:
        return asyncio.run(self._fetch(top_n))

    async def _fetch(self, top_n: int) -> str:
        from playwright.async_api import async_playwright

        api_payloads: list[dict] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="ko-KR",
                timezone_id="Asia/Seoul",
            )

            # webdriver 플래그 숨기기
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            page = await context.new_page()

            # 네트워크 응답 캡처 — 키워드 데이터가 담긴 API 응답을 낚아챔
            async def on_response(response):
                url = response.url
                if response.status != 200:
                    return
                # JSON 응답 중 keyword/trend 관련만
                ct = response.headers.get("content-type", "")
                if "json" not in ct:
                    return
                try:
                    body = await response.body()
                    data = json.loads(body)
                    # 키워드 배열처럼 보이는 응답 저장
                    if isinstance(data, list) and len(data) > 0:
                        api_payloads.append({"url": url, "data": data})
                    elif isinstance(data, dict):
                        api_payloads.append({"url": url, "data": data})
                except Exception:
                    pass

            page.on("response", on_response)

            await page.goto(
                "https://blackkiwi.net/service/trend",
                wait_until="networkidle",
                timeout=30_000,
            )
            # 데이터 바인딩 완료 대기
            await asyncio.sleep(5)

            # ── 방법 1: 캡처된 API 응답에서 키워드 추출 ──────────────
            results = self._parse_api_payloads(api_payloads, top_n)

            # ── 방법 2: DOM에서 직접 추출 (fallback) ─────────────────
            if not results:
                results = await self._parse_dom(page, top_n)

            await browser.close()

        if not results:
            return "블랙키위 트렌드 키워드를 가져오지 못했습니다."

        lines = ["[블랙키위 실시간 트렌드 키워드]", ""]
        for i, (kw, traffic) in enumerate(results, 1):
            lines.append(f"{i:2d}. {kw}  ({traffic})" if traffic else f"{i:2d}. {kw}")

        keywords_only = [kw for kw, _ in results]
        lines.append("")
        lines.append(f"KEYWORD_LIST: {' | '.join(keywords_only)}")
        return "\n".join(lines)

    def _parse_api_payloads(self, payloads: list, top_n: int) -> list[tuple]:
        """캡처된 JSON API 응답에서 키워드 목록 추출 시도."""
        results = []
        seen = set()

        for payload in payloads:
            data = payload["data"]
            items = data if isinstance(data, list) else data.get("data", data.get("result", data.get("keywords", [])))
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue
                # 키워드 필드 후보
                kw = (
                    item.get("keyword")
                    or item.get("name")
                    or item.get("title")
                    or item.get("word")
                    or item.get("searchWord")
                )
                if not kw or not isinstance(kw, str):
                    continue
                if kw in seen:
                    continue
                seen.add(kw)

                # 트래픽 필드 후보
                traffic = (
                    item.get("traffic")
                    or item.get("count")
                    or item.get("searchVolume")
                    or item.get("volume")
                    or ""
                )
                results.append((kw, str(traffic) if traffic else ""))
                if len(results) >= top_n:
                    return results

        return results

    async def _parse_dom(self, page, top_n: int) -> list[tuple]:
        """API 캡처 실패 시 DOM에서 직접 추출."""
        data = await page.evaluate("""
            () => {
                const list = document.getElementById('popularKeywordList');
                if (!list) return [];
                const results = [];
                for (const item of Array.from(list.children)) {
                    let keyword = '';
                    // span[title] — [object Object] 제외
                    for (const span of item.querySelectorAll('span[title]')) {
                        const t = span.getAttribute('title');
                        if (t && !t.includes('[object')) { keyword = t.trim(); break; }
                    }
                    // anchor 텍스트
                    if (!keyword) {
                        for (const a of item.querySelectorAll('a')) {
                            const text = (a.innerText || '').trim();
                            if (text && text.length > 1 && !text.includes('뉴스')) {
                                keyword = text; break;
                            }
                        }
                    }
                    if (!keyword) continue;
                    let traffic = '';
                    for (const child of Array.from(item.children).reverse()) {
                        const text = (child.innerText || '').trim();
                        if (text.startsWith('+')) { traffic = text; break; }
                    }
                    results.push({ keyword, traffic });
                }
                return results;
            }
        """)
        return [(d["keyword"], d.get("traffic", "")) for d in data[:top_n]]
