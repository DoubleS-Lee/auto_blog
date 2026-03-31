import os
import json
import time
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class NaverDataLabInput(BaseModel):
    keywords: list = Field(..., description="트렌드를 분석할 키워드 목록 (최대 5개)")
    start_date: str = Field(default="2024-01-01", description="시작일 (YYYY-MM-DD)")
    end_date: str = Field(default="2025-03-31", description="종료일 (YYYY-MM-DD)")


class NaverDataLabTool(BaseTool):
    name: str = "naver_datalab_trend"
    description: str = "네이버 DataLab API로 키워드 검색 트렌드를 분석한다. 어떤 키워드가 인기 있는지 파악하는 데 사용한다."
    args_schema: type = NaverDataLabInput

    def _run(self, keywords: list, start_date: str = "2024-01-01", end_date: str = "2025-03-31") -> str:
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")

        if not client_id or not client_secret:
            return "오류: NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경변수가 없습니다."

        keyword_groups = [
            {"groupName": kw, "keywords": [kw]}
            for kw in keywords[:5]
        ]

        payload = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": "month",
            "keywordGroups": keyword_groups,
            "device": "mo",
            "ages": [],
            "gender": ""
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
                    results.append(f"키워드: {title} | 평균 검색량: {avg} | 최고 검색량: {peak}")

                return "\n".join(results) if results else "트렌드 데이터 없음"

            except requests.RequestException as e:
                if attempt == 2:
                    return f"DataLab API 오류: {str(e)}"
                time.sleep(2)

        return "DataLab API 요청 실패"
