import os
import json
import time
import requests
from datetime import datetime, timedelta
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class NaverDataLabInput(BaseModel):
    keywords: list = Field(..., description="트렌드를 비교할 키워드 목록 (최대 5개). '이유/원리/왜' 같은 테마 키워드가 아닌 실제 화제 주제 키워드를 넣을 것.")
    period_days: int = Field(default=30, description="오늘로부터 며칠 전까지 분석할지 (기본 30일)")


class NaverDataLabTool(BaseTool):
    name: str = "naver_datalab_trend"
    description: str = (
        "네이버 DataLab API로 키워드 검색 트렌드를 비교한다. "
        "최근 30일 기준으로 어떤 키워드가 더 많이 검색되는지 비교할 때 사용한다. "
        "'이유/원리/왜' 같은 테마 접미사가 아닌 실제 화제 주제 키워드를 입력해야 한다. "
        "예: ['다이어트', 'ChatGPT', '부동산', '여행', '반려동물']"
    )
    args_schema: type = NaverDataLabInput

    def _run(self, keywords: list, period_days: int = 30) -> str:
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")

        if not client_id or not client_secret:
            return "오류: NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경변수가 없습니다."

        # 오늘 기준 동적 날짜 계산
        end_date = datetime.today().strftime("%Y-%m-%d")
        start_date = (datetime.today() - timedelta(days=period_days)).strftime("%Y-%m-%d")

        keyword_groups = [
            {"groupName": kw, "keywords": [kw]}
            for kw in keywords[:5]
        ]

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
                response = requests.post(
                    "https://openapi.naver.com/v1/datalab/search",
                    headers={
                        "X-Naver-Client-Id": client_id,
                        "X-Naver-Client-Secret": client_secret,
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(payload),
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for result in data.get("results", []):
                    title = result["title"]
                    ratios = [d["ratio"] for d in result.get("data", [])]
                    avg = round(sum(ratios) / len(ratios), 1) if ratios else 0
                    peak = round(max(ratios), 1) if ratios else 0
                    results.append(f"키워드: {title} | 최근{period_days}일 평균: {avg} | 최고: {peak}")

                return "\n".join(results) if results else "트렌드 데이터 없음"

            except requests.RequestException as e:
                if attempt == 2:
                    return f"DataLab API 오류: {str(e)}"
                time.sleep(2)

        return "DataLab API 요청 실패"
