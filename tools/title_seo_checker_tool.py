import re
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


# 네이버 블로그 SEO에 효과적인 파워워드
POWER_WORDS = [
    "이유", "원리", "방법", "비밀", "진짜", "사실", "알고보면", "몰랐던",
    "충격", "반전", "놀라운", "효과적인", "필수", "중요한", "핵심",
    "쉽게", "간단한", "완벽한", "최고의", "최악의", "도움이 되는",
]

# 클릭률을 낮추는 패턴
WEAK_PATTERNS = [
    r"^(안녕|오늘|요즘|최근|요즘은|이번에)",  # 두루뭉술 시작
    r"\?$",  # 의문형 끝 (단언형이 더 효과적)
]


class TitleSEOInput(BaseModel):
    title: str = Field(..., description="SEO 품질을 검사할 블로그 제목")
    main_keyword: str = Field(..., description="제목에 포함되어야 할 메인 키워드")


class TitleSEOCheckerTool(BaseTool):
    name: str = "title_seo_checker"
    description: str = (
        "블로그 제목의 네이버 SEO 품질을 검사한다. "
        "제목 길이, 메인 키워드 위치, 파워워드 포함 여부, 클릭 유도 패턴 등을 분석하여 "
        "점수(0~100)와 개선 제안을 반환한다. "
        "점수가 75 미만이면 제목을 반드시 수정하고 다시 검사할 것."
    )
    args_schema: type = TitleSEOInput

    def _run(self, title: str, main_keyword: str) -> str:
        score = 100
        checks = []

        # ── 1. 제목 길이 (20~35자 최적) ──────────────────────
        length = len(title)
        if 20 <= length <= 35:
            checks.append(f"✓ 길이: {length}자 (최적 범위 20~35자)")
        elif length < 15:
            checks.append(f"✗ 길이: {length}자 (너무 짧음 — 정보가 부족해 보임)")
            score -= 20
        elif length < 20:
            checks.append(f"△ 길이: {length}자 (약간 짧음 — 20~35자 권장)")
            score -= 10
        elif length <= 40:
            checks.append(f"△ 길이: {length}자 (약간 긺 — 검색 결과에서 잘릴 수 있음)")
            score -= 5
        else:
            checks.append(f"✗ 길이: {length}자 (너무 긺 — 40자 이하 권장)")
            score -= 15

        # ── 2. 메인 키워드 포함 및 위치 ────────────────────────
        kw_pos = title.find(main_keyword)
        if kw_pos == -1:
            checks.append(f"✗ 메인 키워드 '{main_keyword}' 없음 (반드시 포함해야 함)")
            score -= 30
        elif kw_pos <= 8:
            checks.append(f"✓ 메인 키워드 위치: 앞부분 ('{main_keyword}', {kw_pos + 1}번째 글자) — DIA+ 유리")
        elif kw_pos <= 15:
            checks.append(f"△ 메인 키워드 위치: 중간 ({kw_pos + 1}번째 글자) — 앞으로 이동 권장")
            score -= 8
        else:
            checks.append(f"△ 메인 키워드 위치: 뒷부분 ({kw_pos + 1}번째 글자) — 앞으로 이동 권장")
            score -= 15

        # ── 3. 파워워드 포함 ──────────────────────────────────
        found_pw = [pw for pw in POWER_WORDS if pw in title]
        if len(found_pw) >= 2:
            checks.append(f"✓ 파워워드 {len(found_pw)}개: {', '.join(found_pw)}")
        elif len(found_pw) == 1:
            checks.append(f"△ 파워워드 1개: '{found_pw[0]}' (1~2개 권장)")
            score -= 5
        else:
            checks.append(f"△ 파워워드 없음 — '이유/방법/진짜/비밀' 등 추가 권장")
            score -= 10

        # ── 4. 숫자 포함 여부 ─────────────────────────────────
        if re.search(r"\d", title):
            checks.append("✓ 숫자 포함 — 구체성 강조로 클릭률 향상")
        else:
            checks.append("△ 숫자 없음 — '3가지 이유', '5분 만에' 등 추가 시 클릭률 향상 가능")

        # ── 5. 의문형 끝 패턴 ─────────────────────────────────
        if title.endswith("?") or title.endswith("？"):
            checks.append("△ 의문형 끝 — 단언형('~이다', '~한 이유')이 클릭률에 더 유리")
            score -= 5

        # ── 6. 두루뭉술 시작 패턴 ─────────────────────────────
        for pattern in WEAK_PATTERNS[:1]:  # 시작 패턴만 체크
            if re.match(pattern, title):
                checks.append("△ 두루뭉술한 시작 — 메인 키워드 또는 파워워드로 시작 권장")
                score -= 8
                break

        # ── 7. 중복 단어 ──────────────────────────────────────
        words = [w for w in re.split(r"\s+", title) if len(w) >= 2]
        duplicates = [w for w in set(words) if words.count(w) > 1]
        if duplicates:
            checks.append(f"△ 중복 단어: {', '.join(duplicates)} — 제거 권장")
            score -= 5

        # ── 등급 산정 ─────────────────────────────────────────
        score = max(0, score)
        if score >= 90:
            grade, comment = "S", "최적화 완료"
        elif score >= 75:
            grade, comment = "A", "양호 — 발행 가능"
        elif score >= 60:
            grade, comment = "B", "보통 — 개선 후 발행 권장"
        else:
            grade, comment = "C", "미흡 — 반드시 수정 후 재검사"

        lines = [
            f"[제목 SEO 검사 결과]",
            f"제목: {title}",
            f"메인 키워드: {main_keyword}",
            f"SEO 점수: {score}점 / {grade}등급 ({comment})",
            "",
        ] + checks

        if score < 75:
            lines += [
                "",
                "⚠ 점수 75 미만 — 아래 항목을 개선 후 반드시 재검사하세요:",
                *[f"  · {c}" for c in checks if c.startswith(("✗", "△"))],
            ]

        return "\n".join(lines)
