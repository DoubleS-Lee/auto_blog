import os
import json
import time
import requests
from datetime import datetime, timedelta
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


DATALAB_BATCH_SIZE = 5


class BlogCompetitionInput(BaseModel):
    keywords: list = Field(
        ...,
        description=(
            "SEO 경쟁도와 KEI를 분석할 명사형 키워드 목록. "
            "문장이 아닌 명사 키워드를 입력할 것. "
            "예: ['마그네슘', '러닝화', '레티놀', '유산균', '프로틴']"
        )
    )


class NaverBlogCompetitionTool(BaseTool):
    name: str = "naver_blog_competition"
    description: str = (
        "명사형 키워드에 대해 DataLab 검색량 + 블로그 경쟁 포스팅 수를 동시에 조회하고 "
        "KEI(검색량 ÷ 경쟁수)를 계산하여 SEO 기회 점수를 반환한다. "
        "검색량이 높고 경쟁이 낮을수록 KEI가 높아 노출에 유리하다. "
        "키워드는 명사형으로 입력할 것 (문장 입력 시 경쟁도가 낮게 측정되어 무의미)."
    )
    args_schema: type = BlogCompetitionInput

    # ── DataLab 검색량 조회 ──────────────────────────────────

    def _fetch_datalab_batch(
        self,
        client_id: str,
        client_secret: str,
        batch: list,
        start_date: str,
        end_date: str,
    ) -> dict:
        """DataLab API 1회 호출 (최대 5개) → {keyword: avg_ratio}"""
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
                    return {kw: 0 for kw in batch}
                time.sleep(2)
        return {kw: 0 for kw in batch}

    def _fetch_search_volumes(
        self,
        client_id: str,
        client_secret: str,
        keywords: list,
    ) -> dict:
        """전체 키워드 검색량 조회 (5개씩 배치) → {keyword: avg_ratio}"""
        end_date = datetime.today().strftime("%Y-%m-%d")
        start_date = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")

        volumes = {}
        batches = [keywords[i:i + DATALAB_BATCH_SIZE] for i in range(0, len(keywords), DATALAB_BATCH_SIZE)]
        for batch in batches:
            volumes.update(self._fetch_datalab_batch(client_id, client_secret, batch, start_date, end_date))
            time.sleep(0.5)
        return volumes

    # ── 블로그 경쟁도 조회 ───────────────────────────────────

    def _fetch_competition(
        self,
        client_id: str,
        client_secret: str,
        keyword: str,
    ) -> dict:
        """블로그 검색 API → 경쟁 포스팅 수 + 최근 30일 신규 글 수"""
        try:
            resp = requests.get(
                "https://openapi.naver.com/v1/search/blog.json",
                headers={
                    "X-Naver-Client-Id": client_id,
                    "X-Naver-Client-Secret": client_secret,
                },
                params={"query": keyword, "display": 10, "sort": "sim"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            total = data.get("total", 0)
            items = data.get("items", [])

            cutoff = datetime.now() - timedelta(days=30)
            recent_count = sum(
                1 for item in items
                if self._parse_date(item.get("postdate", "")) >= cutoff
            )

            return {"total": total, "recent_count": recent_count, "error": None}

        except requests.RequestException as e:
            return {"total": 0, "recent_count": 0, "error": str(e)}

    def _parse_date(self, postdate: str) -> datetime:
        try:
            return datetime.strptime(postdate, "%Y%m%d")
        except ValueError:
            return datetime.min

    # ── KEI 등급 ─────────────────────────────────────────────

    def _kei_grade(self, kei: float) -> tuple:
        """KEI = DataLab 평균비율 / (경쟁수 / 1000) 기반 등급"""
        if kei >= 20:
            return "★★★★★", "황금 키워드"
        elif kei >= 10:
            return "★★★★☆", "유망"
        elif kei >= 3:
            return "★★★☆☆", "보통"
        elif kei >= 1:
            return "★★☆☆☆", "경쟁 어려움"
        else:
            return "★☆☆☆☆", "포화 상태"

    # ── 메인 실행 ─────────────────────────────────────────────

    def _run(self, keywords: list) -> str:
        client_id = os.environ.get("NAVER_CLIENT_ID")
        client_secret = os.environ.get("NAVER_CLIENT_SECRET")
        if not client_id or not client_secret:
            return "오류: NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 환경변수가 없습니다."

        # 1. 검색량 (DataLab)
        print(f"[BlogCompetition] DataLab 검색량 조회 중... ({len(keywords)}개 키워드)")
        volumes = self._fetch_search_volumes(client_id, client_secret, keywords)

        # 2. 경쟁도 (블로그 검색)
        results = []
        for kw in keywords:
            comp = self._fetch_competition(client_id, client_secret, kw)
            search_vol = volumes.get(kw, 0)
            total = comp["total"]

            # KEI = 검색량 / (경쟁수 / 1000)
            # 경쟁수 0이면 검색량 그대로 사용 (블루오션)
            if total > 0:
                kei = round(search_vol / (total / 1000), 2)
            else:
                kei = search_vol * 10  # 경쟁 없음 = 최고 점수

            stars, grade = self._kei_grade(kei)

            results.append({
                "keyword": kw,
                "search_vol": search_vol,
                "total": total,
                "recent_count": comp["recent_count"],
                "kei": kei,
                "stars": stars,
                "grade": grade,
                "error": comp["error"],
            })
            time.sleep(0.3)

        # KEI 내림차순 정렬
        results.sort(key=lambda x: x["kei"], reverse=True)

        lines = ["[네이버 블로그 SEO 기회 분석 — 검색량 · 경쟁수 · KEI]", ""]
        for r in results:
            if r["error"]:
                lines.append(f"✗ {r['keyword']} — 조회 실패: {r['error']}")
                continue
            lines.append(f"{r['stars']} {r['keyword']}  [{r['grade']}]")
            lines.append(
                f"   검색량: {r['search_vol']}  |  "
                f"경쟁 포스팅: {r['total']:,}개  |  "
                f"최근 30일 신규: {r['recent_count']}개  |  "
                f"KEI: {r['kei']}"
            )
            lines.append("")

        lines += [
            "─────────────────────────────────────────",
            "※ KEI = DataLab 검색량 ÷ (경쟁수 ÷ 1000)  — 높을수록 좋음",
            "※ ★★★★★(KEI≥20): 황금 키워드   ★★★★☆(KEI≥10): 유망",
            "※ ★★★☆☆(KEI≥3): 보통   ★★☆☆☆(KEI≥1): 어려움   ★☆☆☆☆: 포화",
            "※ 별 4~5개(★★★★☆ 이상) 키워드를 우선 선정할 것",
        ]
        return "\n".join(lines)
