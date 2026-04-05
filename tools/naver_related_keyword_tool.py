import os
import re
import json
import time
import requests
from datetime import datetime, timedelta
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class RelatedKeywordInput(BaseModel):
    keyword: str = Field(
        ...,
        description="파생 키워드를 발굴할 메인 명사 키워드. 예: '마그네슘', '러닝화', '레티놀'"
    )
    top_n: int = Field(default=10, description="반환할 상위 파생 키워드 수 (기본 10)")


class NaverRelatedKeywordTool(BaseTool):
    name: str = "naver_related_keyword"
    description: str = (
        "네이버 자동완성 API로 실제 사람들이 검색하는 파생 키워드를 가져온 뒤, "
        "DataLab으로 검색량을 검증해 실측 데이터 기반 순위로 반환한다. "
        "하드코딩 패턴 없이 도메인에 상관없이 어떤 키워드에도 사용 가능하다."
    )
    args_schema: type = RelatedKeywordInput

    _AC_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.naver.com/",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    # ── 1단계: 네이버 자동완성 ─────────────────────────────

    def _fetch_autocomplete(self, keyword: str) -> list:
        """네이버 검색창 자동완성 API → 실제 검색어 후보 목록 반환."""
        try:
            resp = requests.get(
                "https://ac.search.naver.com/nx/ac",
                params={
                    "q": keyword,
                    "con": "0",
                    "frm": "nv",
                    "ans": "2",
                    "r_format": "json",
                    "r_enc": "UTF-8",
                    "r_unicode": "0",
                    "t_koreng": "1",
                    "run": "2",
                    "rev": "4",
                    "q_enc": "UTF-8",
                    "st": "100",
                },
                headers=self._AC_HEADERS,
                timeout=8,
            )
            resp.raise_for_status()

            # JSONP 래퍼 제거: _jsonp_0({...}) → {...}
            text = resp.text.strip()
            m = re.match(r'^[^(]+\((.*)\)\s*$', text, re.DOTALL)
            data = json.loads(m.group(1) if m else text)

            # items[0] = [[키워드, "0"], ...]
            items = data.get("items", [[]])[0]
            suggestions = [item[0] for item in items if item and item[0] != keyword]
            return suggestions

        except Exception as e:
            print(f"[RelatedKeyword] 자동완성 오류: {e}")
            return []

    # ── 2단계: DataLab 검색량 검증 ────────────────────────

    def _fetch_datalab_batch(
        self,
        client_id: str,
        client_secret: str,
        keywords: list,
        start_date: str,
        end_date: str,
    ) -> dict:
        """DataLab 1회 호출 (최대 5개) → {keyword: avg_ratio}"""
        keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in keywords]
        payload = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": "week",
            "keywordGroups": keyword_groups,
            "device": "mo",
            "ages": [],
            "gender": "",
        }
        for attempt in range(3):
            try:
                resp = requests.post(
                    "https://openapi.naver.com/v1/datalab/search",
                    headers={
                        "X-Naver-Client-Id": client_id,
                        "X-Naver-Client-Secret": client_secret,
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(payload),
                    timeout=10,
                )
                resp.raise_for_status()
                result = {}
                for item in resp.json().get("results", []):
                    ratios = [d["ratio"] for d in item.get("data", [])]
                    avg = round(sum(ratios) / len(ratios), 1) if ratios else 0
                    result[item["title"]] = avg
                return result
            except requests.RequestException:
                if attempt == 2:
                    return {kw: 0 for kw in keywords}
                time.sleep(2)
        return {kw: 0 for kw in keywords}

    def _validate_with_datalab(
        self,
        client_id: str,
        client_secret: str,
        keywords: list,
    ) -> dict:
        """전체 후보 키워드 DataLab 검색량 조회 (5개씩 배치)"""
        end_date = datetime.today().strftime("%Y-%m-%d")
        start_date = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")

        volumes = {}
        batches = [keywords[i:i + 5] for i in range(0, len(keywords), 5)]
        for batch in batches:
            volumes.update(
                self._fetch_datalab_batch(client_id, client_secret, batch, start_date, end_date)
            )
            time.sleep(0.5)
        return volumes

    # ── 메인 실행 ─────────────────────────────────────────

    def _run(self, keyword: str, top_n: int = 10) -> str:
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")
        if not client_id or not client_secret:
            return "오류: NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경변수가 없습니다."

        # 1. 자동완성으로 실제 검색어 후보 수집
        suggestions = self._fetch_autocomplete(keyword)
        if not suggestions:
            return (
                f"['{keyword}' 파생 키워드]\n"
                "자동완성 결과가 없습니다.\n"
                f"RELATED_KEYWORDS: {keyword}"
            )

        # 2. DataLab으로 검색량 검증
        volumes = self._validate_with_datalab(client_id, client_secret, suggestions)

        # 3. 검색량 > 0 필터링 후 내림차순 정렬
        valid = [(kw, vol) for kw, vol in volumes.items() if vol > 0]
        valid.sort(key=lambda x: x[1], reverse=True)

        # 검색량 0이어도 자동완성에 있다면 일단 후보에 포함 (DataLab 기간 밖일 수 있음)
        if not valid:
            valid = [(kw, 0) for kw in suggestions]

        top = valid[:top_n]

        lines = [
            f"['{keyword}' 파생 키워드 — 네이버 자동완성 + DataLab 검색량 검증]",
            f"자동완성 후보 {len(suggestions)}개 → 실검색량 확인 {len([v for v in valid if v[1] > 0])}개",
            "",
        ]
        for rank, (kw, vol) in enumerate(top, 1):
            vol_str = str(vol) if vol > 0 else "미미"
            lines.append(f"{rank}위 | {kw} | 검색량: {vol_str}")

        kw_list = " | ".join(kw for kw, _ in top)
        lines.append(f"\nRELATED_KEYWORDS: {kw_list}")

        return "\n".join(lines)
