import os
import re
import json
import time
import requests
from collections import Counter
from datetime import datetime, timedelta
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


# 블로그 주제와 연관성 높은 쇼핑 카테고리 (최대 3개씩 3배치 — API 한도)
CATEGORY_BATCHES = [
    [
        {"name": "식품", "param": ["50000008"]},
        {"name": "생활/건강", "param": ["50000007"]},
        {"name": "스포츠/레저", "param": ["50000006"]},
    ],
    [
        {"name": "디지털/가전", "param": ["50000003"]},
        {"name": "화장품/미용", "param": ["50000002"]},
        {"name": "반려동물용품", "param": ["50000011"]},
    ],
    [
        {"name": "도서", "param": ["50000005"]},
        {"name": "출산/육아", "param": ["50000010"]},
        {"name": "패션의류", "param": ["50000000"]},
    ],
]

# 쇼핑 상품명에서 걸러낼 일반 불용어
STOPWORDS = {
    "ml", "g", "kg", "l", "mg", "mm", "cm", "개", "세트", "팩", "박스",
    "구매", "판매", "상품", "제품", "정품", "무료", "배송", "할인", "특가",
    "추천", "인기", "베스트", "신상", "공식", "정식", "국내", "해외", "수입",
    "포함", "증정", "이상", "이하", "이내", "미만", "초과",
}


class ShoppingInsightInput(BaseModel):
    period_days: int = Field(default=30, description="오늘로부터 며칠 전까지 분석할지 (기본 30일)")
    top_categories: int = Field(default=5, description="키워드를 추출할 상위 카테고리 수 (기본 5)")
    keywords_per_category: int = Field(default=8, description="카테고리당 추출할 인기 키워드 수 (기본 8)")


class NaverShoppingInsightTool(BaseTool):
    name: str = "naver_shopping_insight"
    description: str = (
        "네이버 쇼핑인사이트로 지금 가장 핫한 카테고리를 파악한 뒤, "
        "해당 카테고리에서 사람들이 실제로 검색하는 인기 키워드를 추출한다. "
        "예: 식품 카테고리 1위 → '프로틴', '닭가슴살', '간헐적단식' 등 실제 검색 키워드 반환. "
        "이 키워드들을 '왜 그럴까?' 각도와 연결해 블로그 주제로 발전시킨다."
    )
    args_schema: type = ShoppingInsightInput

    # ── 1단계: 카테고리 트렌드 순위 ──────────────────────────

    def _fetch_category_trends(
        self,
        client_id: str,
        client_secret: str,
        start_date: str,
        end_date: str,
    ) -> list:
        """모든 카테고리 배치 호출 → [(카테고리명, 최근비율)] 내림차순 반환."""
        all_results = []
        for batch in CATEGORY_BATCHES:
            payload = {
                "startDate": start_date,
                "endDate": end_date,
                "timeUnit": "week",
                "category": batch,
            }
            for attempt in range(3):
                try:
                    resp = requests.post(
                        "https://openapi.naver.com/v1/datalab/shopping/categories",
                        headers={
                            "X-Naver-Client-Id": client_id,
                            "X-Naver-Client-Secret": client_secret,
                            "Content-Type": "application/json",
                        },
                        data=json.dumps(payload),
                        timeout=10,
                    )
                    if not resp.ok:
                        print(f"[ShoppingInsight] 카테고리 트렌드 오류 {resp.status_code}: {resp.text}")
                        break
                    for item in resp.json().get("results", []):
                        ratios = [d["ratio"] for d in item.get("data", []) if "ratio" in d]
                        recent = round(ratios[-1], 1) if ratios else 0
                        all_results.append((item.get("title", ""), recent))
                    break
                except requests.RequestException as e:
                    if attempt == 2:
                        print(f"[ShoppingInsight] 배치 요청 실패: {e}")
                    else:
                        time.sleep(2)
            time.sleep(0.5)

        all_results.sort(key=lambda x: x[1], reverse=True)
        return all_results

    # ── 2단계: 카테고리별 인기 키워드 추출 ──────────────────

    def _extract_keywords(self, titles: list, top_n: int) -> list:
        """상품명 목록에서 빈도 기반 인기 키워드 추출."""
        word_counter: Counter = Counter()
        for title in titles:
            # HTML 태그 제거
            clean = re.sub(r"<[^>]+>", "", title)
            # 특수문자·숫자 제거 후 공백 분리
            words = re.split(r"[\s\[\]()（）/·,+&\-_]+", clean)
            for w in words:
                w = w.strip()
                # 한글 2글자 이상, 불용어 제외
                if len(w) >= 2 and re.search(r"[가-힣]", w) and w not in STOPWORDS:
                    word_counter[w] += 1
        return [word for word, _ in word_counter.most_common(top_n)]

    def _fetch_category_keywords(
        self,
        client_id: str,
        client_secret: str,
        category_name: str,
        keywords_per_category: int,
    ) -> list:
        """쇼핑 검색 API로 카테고리 내 인기 상품명 수집 → 키워드 추출."""
        try:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/shop.json",
                headers={
                    "X-Naver-Client-Id": client_id,
                    "X-Naver-Client-Secret": client_secret,
                },
                params={"query": category_name, "display": 100, "sort": "sim"},
                timeout=10,
            )
            if not resp.ok:
                print(f"[ShoppingInsight] 쇼핑검색 오류 {resp.status_code}: {resp.text}")
                return []
            titles = [item.get("title", "") for item in resp.json().get("items", [])]
            return self._extract_keywords(titles, top_n=keywords_per_category)
        except requests.RequestException as e:
            print(f"[ShoppingInsight] 쇼핑검색 요청 실패 ({category_name}): {e}")
            return []

    # ── 메인 실행 ────────────────────────────────────────────

    def _run(
        self,
        period_days: int = 30,
        top_categories: int = 5,
        keywords_per_category: int = 8,
    ) -> str:
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")
        if not client_id or not client_secret:
            return "오류: NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경변수가 없습니다."

        end_date = datetime.today().strftime("%Y-%m-%d")
        start_date = (datetime.today() - timedelta(days=period_days)).strftime("%Y-%m-%d")

        # 1단계: 카테고리 순위
        trends = self._fetch_category_trends(client_id, client_secret, start_date, end_date)
        if not trends:
            return "쇼핑인사이트 카테고리 트렌드를 가져오지 못했습니다."

        top = trends[:top_categories]

        # 2단계: 상위 카테고리별 인기 키워드
        lines = [f"[쇼핑인사이트 — 최근 {period_days}일 기준 상위 {top_categories}개 카테고리 인기 키워드]", ""]
        for rank, (cat_name, recent_ratio) in enumerate(top, 1):
            keywords = self._fetch_category_keywords(
                client_id, client_secret, cat_name, keywords_per_category
            )
            kw_str = ", ".join(keywords) if keywords else "(키워드 추출 실패)"
            lines.append(f"{rank}위 카테고리: {cat_name} (클릭비율 {recent_ratio})")
            lines.append(f"   → 인기 키워드: {kw_str}")
            lines.append("")
            time.sleep(0.3)

        lines.append("※ 위 키워드 = 지금 사람들이 네이버 쇼핑에서 실제로 검색하는 소재")
        lines.append("※ 각 키워드에서 '왜 그럴까?' 각도의 블로그 주제를 도출할 것")

        return "\n".join(lines)
