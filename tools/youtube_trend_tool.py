import os
import time
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class YouTubeTrendInput(BaseModel):
    keyword: str = Field(
        ...,
        description="글로벌 흥행 영상을 검색할 명사형 키워드. 예: 'magnesium', 'protein', 'running shoes'"
    )
    max_results: int = Field(default=5, description="반환할 영상 수 (기본 5개)")
    region_code: str = Field(default="US", description="검색 지역 코드. 글로벌 흥행은 'US' 권장")
    min_views: int = Field(default=500_000, description="최소 조회수 필터 (기본 50만)")


class YouTubeTrendTool(BaseTool):
    name: str = "youtube_trend"
    description: str = (
        "YouTube Data API로 키워드의 글로벌 인기 영상을 검색한다. "
        "조회수가 높은 영상 제목에서 '충격적·반전·의외' 스토리텔링 패턴을 파악한다. "
        "글로벌에서 이미 검증된 흥미 포인트를 한국 블로그 주제로 변환하는 소재로 사용한다. "
        "키워드는 영어로 입력해야 글로벌 결과를 얻을 수 있다."
    )
    args_schema: type = YouTubeTrendInput

    def _search_videos(self, api_key: str, keyword: str, region_code: str, max_fetch: int = 15) -> list:
        """YouTube Search API로 인기 영상 ID 목록 조회."""
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "key": api_key,
                "q": keyword,
                "type": "video",
                "order": "viewCount",
                "regionCode": region_code,
                "relevanceLanguage": "en",
                "maxResults": max_fetch,
                "part": "id,snippet",
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [
            {
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "published": item["snippet"]["publishedAt"][:10],
            }
            for item in items
            if item.get("id", {}).get("videoId")
        ]

    def _fetch_statistics(self, api_key: str, video_ids: list) -> dict:
        """YouTube Videos API로 영상 통계(조회수) 조회."""
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "key": api_key,
                "id": ",".join(video_ids),
                "part": "statistics",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return {
            item["id"]: int(item["statistics"].get("viewCount", 0))
            for item in resp.json().get("items", [])
        }

    def _run(
        self,
        keyword: str,
        max_results: int = 5,
        region_code: str = "US",
        min_views: int = 500_000,
    ) -> str:
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            return "오류: YOUTUBE_API_KEY 환경변수가 없습니다."

        try:
            # 1. 검색
            candidates = self._search_videos(api_key, keyword, region_code)
            if not candidates:
                return f"'{keyword}' 검색 결과가 없습니다."

            # 2. 통계 조회
            video_ids = [v["video_id"] for v in candidates]
            stats = self._fetch_statistics(api_key, video_ids)

            # 3. 조회수 붙이기 + 필터 + 정렬
            for v in candidates:
                v["views"] = stats.get(v["video_id"], 0)

            filtered = [v for v in candidates if v["views"] >= min_views]
            filtered.sort(key=lambda x: x["views"], reverse=True)
            top = filtered[:max_results]

            if not top:
                # 필터 기준 미달 시 상위 결과라도 반환
                top = sorted(candidates, key=lambda x: x["views"], reverse=True)[:max_results]

        except requests.RequestException as e:
            return f"YouTube API 오류: {e}"

        # 4. 포맷 출력
        lines = [
            f"[YouTube 글로벌 흥행 분석 — 키워드: '{keyword}' / 지역: {region_code}]",
            "",
        ]
        for i, v in enumerate(top, 1):
            views_str = f"{v['views']:,}"
            lines.append(f"{i}. {v['title']}")
            lines.append(f"   조회수: {views_str}회 | 채널: {v['channel']} | 게시일: {v['published']}")
            lines.append("")

        lines += [
            "─────────────────────────────────────────",
            "※ 위 영상들의 제목 패턴을 분석하여 '세상 모든 것에는 이유가 있다' 블로그 주제로 변환할 것",
            "※ 평가 기준:",
            "   ① 메인 키워드(명사)가 주제에 포함되는가?",
            "   ② 뻔하지 않고 충격적/반전/의외의 정보인가?",
            "   ③ 글로벌 트렌드를 기반으로 한 인사이트인가?",
            "   → 3가지 모두 충족 시 '합격' 주제로 채택",
        ]

        return "\n".join(lines)
