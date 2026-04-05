import os
import json
import time
import requests
from datetime import datetime, timedelta
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


DATALAB_BATCH_SIZE = 5  # API 한 번에 최대 5개


class NaverDataLabInput(BaseModel):
    keywords: list = Field(
        ...,
        description=(
            "트렌드를 비교할 키워드 목록 (최대 20개). "
            "'이유/원리/왜' 같은 테마 키워드가 아닌 실제 명사형 키워드를 넣을 것. "
            "예: ['마그네슘', '프로틴', '러닝화', '레티놀', '닭가슴살', '유산균', '오메가3', '폼롤러', '선크림', '간헐적단식', ...]"
        )
    )
    period_days: int = Field(default=30, description="오늘로부터 며칠 전까지 분석할지 (기본 30일)")


class NaverDataLabTool(BaseTool):
    name: str = "naver_datalab_trend"
    description: str = (
        "네이버 DataLab API로 키워드 검색 트렌드를 비교한다. "
        "최대 20개 키워드를 한 번에 비교할 수 있다 (내부적으로 5개씩 4배치 처리). "
        "최근 30일 기준 평균·최고 검색량 비교로 상승 중인 키워드를 선별할 때 사용한다. "
        "'이유/원리/왜' 같은 테마 접미사가 아닌 명사형 키워드를 입력해야 한다."
    )
    args_schema: type = NaverDataLabInput

    def _fetch_batch(
        self,
        client_id: str,
        client_secret: str,
        batch: list,
        start_date: str,
        end_date: str,
        period_days: int,
    ) -> list:
        """키워드 배치 1회 호출 → [(키워드, 평균, 최고)] 반환."""
        keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in batch]
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

                results = []
                for result in response.json().get("results", []):
                    ratios = [d["ratio"] for d in result.get("data", [])]
                    avg = round(sum(ratios) / len(ratios), 1) if ratios else 0
                    peak = round(max(ratios), 1) if ratios else 0
                    results.append((result["title"], avg, peak))
                return results

            except requests.RequestException as e:
                if attempt == 2:
                    return [(kw, 0, 0) for kw in batch]
                time.sleep(2)

        return [(kw, 0, 0) for kw in batch]

    def _run(self, keywords: list, period_days: int = 30) -> str:
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")

        if not client_id or not client_secret:
            return "오류: NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경변수가 없습니다."

        end_date = datetime.today().strftime("%Y-%m-%d")
        start_date = (datetime.today() - timedelta(days=period_days)).strftime("%Y-%m-%d")

        # 최대 20개, 5개씩 배치 분리
        targets = keywords[:20]
        batches = [targets[i:i + DATALAB_BATCH_SIZE] for i in range(0, len(targets), DATALAB_BATCH_SIZE)]

        all_results = []
        for batch in batches:
            batch_results = self._fetch_batch(
                client_id, client_secret, batch, start_date, end_date, period_days
            )
            all_results.extend(batch_results)
            time.sleep(0.5)

        if not all_results:
            return "트렌드 데이터 없음"

        # 평균 검색량 기준 내림차순 정렬
        all_results.sort(key=lambda x: x[1], reverse=True)

        lines = [f"[DataLab 검색 트렌드 — 최근 {period_days}일]"]
        for rank, (title, avg, peak) in enumerate(all_results, 1):
            lines.append(f"{rank}위 | {title} | 평균: {avg} | 최고: {peak}")

        return "\n".join(lines)
