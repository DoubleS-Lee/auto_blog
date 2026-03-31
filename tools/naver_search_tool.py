import os
import time
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class NaverSearchInput(BaseModel):
    query: str = Field(..., description="검색할 키워드")
    display: int = Field(default=10, description="가져올 결과 수 (최대 100)")


class NaverSearchTool(BaseTool):
    name: str = "naver_blog_search"
    description: str = "네이버 검색 API로 특정 키워드의 상위 블로그 글을 검색한다. 경쟁 글 분석과 제목/내용 패턴 파악에 사용한다."
    args_schema: type = NaverSearchInput

    def _run(self, query: str, display: int = 10) -> str:
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")

        if not client_id or not client_secret:
            return "오류: NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경변수가 없습니다."

        for attempt in range(3):
            try:
                response = requests.get(
                    "https://openapi.naver.com/v1/search/blog",
                    headers={
                        "X-Naver-Client-Id": client_id,
                        "X-Naver-Client-Secret": client_secret,
                    },
                    params={
                        "query": query,
                        "display": min(display, 10),
                        "sort": "sim",
                    },
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()

                items = data.get("items", [])
                if not items:
                    return f"'{query}' 검색 결과 없음"

                results = []
                for i, item in enumerate(items, 1):
                    title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                    description = item.get("description", "").replace("<b>", "").replace("</b>", "")
                    results.append(f"{i}. 제목: {title}\n   요약: {description}")

                return "\n\n".join(results)

            except requests.RequestException as e:
                if attempt == 2:
                    return f"검색 API 오류: {str(e)}"
                time.sleep(2)

        return "검색 API 요청 실패"
