import os
import re
import time
import requests
from collections import Counter
from datetime import datetime
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


# 카테고리별 검색 쿼리 (뉴스 80건 수집에 사용)
CATEGORY_QUERIES = {
    "IT":   ["인공지능", "스마트폰"],
    "경제":  ["주식", "부동산"],
    "건강":  ["건강", "의료"],
    "교육":  ["교육", "입시"],
    "여행":  ["여행", "관광"],
    "생활":  ["소비", "생활용품"],
    "육아":  ["육아", "임신"],
    "시사":  ["사회이슈", "정치"],
}

VALID_CATEGORIES = list(CATEGORY_QUERIES.keys())

# 뉴스 제목에서 걸러낼 불용어
NEWS_STOPWORDS = {
    # 조사·접속사
    "의", "가", "이", "은", "는", "을", "를", "에", "와", "과", "도", "로", "으로",
    "에서", "부터", "까지", "에게", "한테", "보다", "처럼", "만큼", "마다",
    # 일반 동사·형용사 어근
    "하다", "있다", "없다", "되다", "않다", "위한", "대한", "통한", "따른",
    "위해", "대해", "통해", "관련", "따라", "통해",
    # 뉴스 공통 표현
    "발표", "공개", "개최", "진행", "예정", "실시", "추진", "제공", "운영",
    "지원", "확대", "강화", "개선", "시행", "도입", "적용",
    "국내", "해외", "전국", "전세계", "글로벌", "현재", "이번", "최근",
    "지난", "오늘", "내일", "올해", "작년", "다음", "이후",
    "기자", "뉴스", "기사", "보도", "취재", "사진", "영상",
    "정부", "관계자", "전문가", "업계", "관계부처",
    "사람", "경우", "부분", "내용", "결과", "방법", "문제", "상황",
    "이유", "원인", "효과", "영향", "변화", "기준", "수준",
    "최고", "최대", "최소", "최저", "역대", "사상",
}


class NaverNewsTrendInput(BaseModel):
    category: str = Field(
        ...,
        description=(
            "분석할 뉴스 카테고리. "
            "선택 가능: IT / 경제 / 건강 / 교육 / 여행 / 생활 / 육아 / 시사"
        )
    )
    count: int = Field(default=80, description="수집할 뉴스 건수 (기본 80, 최대 160)")
    top_keywords: int = Field(default=20, description="반환할 상위 키워드 수 (기본 20)")


class NaverNewsTrendTool(BaseTool):
    name: str = "naver_news_trend"
    description: str = (
        "네이버 뉴스 검색 API로 선택한 카테고리의 최신 뉴스를 수집하고 "
        "뉴스 제목에서 자주 등장하는 키워드를 빈도순으로 추출한다. "
        "카테고리: IT / 경제 / 건강 / 교육 / 여행 / 생활 / 육아 / 시사"
    )
    args_schema: type = NaverNewsTrendInput

    def _fetch_news(
        self,
        client_id: str,
        client_secret: str,
        query: str,
        display: int,
    ) -> list:
        """단일 쿼리로 뉴스 제목 목록 반환."""
        try:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/news.json",
                headers={
                    "X-Naver-Client-Id": client_id,
                    "X-Naver-Client-Secret": client_secret,
                },
                params={"query": query, "display": min(display, 100), "sort": "date"},
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            # HTML 태그 제거 후 제목 반환
            titles = []
            for item in items:
                raw = item.get("title", "")
                clean = re.sub(r"<[^>]+>", "", raw).strip()
                if clean:
                    titles.append(clean)
            return titles
        except Exception as e:
            print(f"[NaverNews] 뉴스 조회 실패 ({query}): {e}")
            return []

    def _extract_keywords(self, titles: list, top_n: int) -> list:
        """뉴스 제목 목록에서 빈도 기반 핵심 키워드 추출."""
        counter: Counter = Counter()
        for title in titles:
            # 한국어 단어 추출 (2~7글자)
            words = re.findall(r"[가-힣]{2,7}", title)
            for w in words:
                if w not in NEWS_STOPWORDS and not w.isdigit():
                    counter[w] += 1

        # 빈도 1회짜리 제거 (노이즈)
        return [(word, cnt) for word, cnt in counter.most_common(top_n) if cnt >= 2]

    def _run(self, category: str, count: int = 80, top_keywords: int = 20) -> str:
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")
        if not client_id or not client_secret:
            return "오류: NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경변수가 없습니다."

        # 카테고리 유효성 검사
        category = category.strip()
        if category not in CATEGORY_QUERIES:
            return (
                f"오류: 유효하지 않은 카테고리 '{category}'. "
                f"선택 가능: {', '.join(VALID_CATEGORIES)}"
            )

        queries = CATEGORY_QUERIES[category]
        per_query = max(40, count // len(queries))

        all_titles = []
        for q in queries:
            titles = self._fetch_news(client_id, client_secret, q, per_query)
            all_titles.extend(titles)
            time.sleep(0.3)

        if not all_titles:
            return f"[네이버 뉴스] '{category}' 카테고리 뉴스를 가져오지 못했습니다."

        today = datetime.today().strftime("%Y-%m-%d")
        keywords = self._extract_keywords(all_titles, top_keywords)

        if not keywords:
            return f"[네이버 뉴스 키워드 — {category} | {today}]\n키워드를 추출하지 못했습니다."

        lines = [
            f"[네이버 뉴스 키워드 분석 — {category} 카테고리 | {today}]",
            f"수집 뉴스: {len(all_titles)}건 → 상위 {len(keywords)}개 키워드",
            "",
        ]
        for rank, (word, cnt) in enumerate(keywords, 1):
            lines.append(f"{rank}위 | {word} | 빈도: {cnt}회")

        kw_list = " | ".join(word for word, _ in keywords)
        lines.append(f"\nKEYWORD_LIST: {kw_list}")

        return "\n".join(lines)
