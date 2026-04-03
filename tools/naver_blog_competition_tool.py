import os
import re
import time
import requests
from datetime import datetime, timedelta
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class BlogCompetitionInput(BaseModel):
    topics: list = Field(
        ...,
        description="SEO 경쟁도를 분석할 주제 목록. 예: ['마그네슘이 잠에 도움이 되는 이유', '러닝화 쿠션이 부상을 유발하는 이유']"
    )


class NaverBlogCompetitionTool(BaseTool):
    name: str = "naver_blog_competition"
    description: str = (
        "네이버 블로그 검색 API로 주제별 경쟁도를 분석한다. "
        "각 주제의 경쟁 포스팅 수, 최근 30일 신규 글 수, SEO 기회 점수를 반환한다. "
        "검색량이 높고 경쟁이 낮은 주제가 네이버 노출에 유리하다. "
        "추천 주제 목록을 확정하기 전에 반드시 이 툴로 경쟁도를 검증할 것."
    )
    args_schema: type = BlogCompetitionInput

    def _opportunity_rating(self, total: int) -> tuple:
        """경쟁 포스팅 수 기반 기회 점수 산출."""
        if total < 1_000:
            return "★★★★★", "매우 낮음 — 블루오션"
        elif total < 5_000:
            return "★★★★☆", "낮음 — 진입 유리"
        elif total < 20_000:
            return "★★★☆☆", "보통 — 양질 콘텐츠 필요"
        elif total < 50_000:
            return "★★☆☆☆", "높음 — 경쟁 어려움"
        else:
            return "★☆☆☆☆", "매우 높음 — 포화 상태"

    def _fetch_competition(
        self,
        client_id: str,
        client_secret: str,
        topic: str,
    ) -> dict:
        try:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/blog.json",
                headers={
                    "X-Naver-Client-Id": client_id,
                    "X-Naver-Client-Secret": client_secret,
                },
                params={"query": topic, "display": 10, "sort": "sim"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            total = data.get("total", 0)
            items = data.get("items", [])

            # 최근 30일 이내 포스팅 수
            cutoff = datetime.now() - timedelta(days=30)
            recent_count = 0
            for item in items:
                postdate = item.get("postdate", "")
                try:
                    if datetime.strptime(postdate, "%Y%m%d") >= cutoff:
                        recent_count += 1
                except ValueError:
                    pass

            stars, rating = self._opportunity_rating(total)
            return {
                "topic": topic,
                "total": total,
                "recent_count": recent_count,
                "stars": stars,
                "rating": rating,
                "error": None,
            }

        except requests.RequestException as e:
            return {"topic": topic, "total": 0, "recent_count": 0,
                    "stars": "—", "rating": "조회 실패", "error": str(e)}

    def _run(self, topics: list) -> str:
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")
        if not client_id or not client_secret:
            return "오류: NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경변수가 없습니다."

        results = []
        for topic in topics:
            result = self._fetch_competition(client_id, client_secret, topic)
            results.append(result)
            time.sleep(0.3)

        # 기회 점수(별 수) 기준 정렬
        results.sort(key=lambda x: x["stars"], reverse=True)

        lines = ["[네이버 블로그 경쟁도 분석]", ""]
        for r in results:
            if r["error"]:
                lines.append(f"✗ {r['topic']} — 조회 실패: {r['error']}")
                continue
            lines.append(f"{r['stars']} {r['topic']}")
            lines.append(
                f"   경쟁 포스팅: {r['total']:,}개 | "
                f"최근 30일 신규: {r['recent_count']}개 | "
                f"경쟁도: {r['rating']}"
            )
            lines.append("")

        lines.append("※ 별 4~5개 주제를 우선 선정할 것")
        lines.append("※ 별 1~2개(포화 상태) 주제는 제외하거나 더 구체적인 롱테일 키워드로 변경할 것")
        return "\n".join(lines)
