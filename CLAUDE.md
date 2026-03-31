# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

사주 관련 정보 블로그(개인 운세 풀이 X, 개념/지식/원리 정보 O)를 자동으로 생성하고 네이버 블로그에 발행하는 시스템.
주제를 입력하면 5개 CrewAI 에이전트가 순차적으로 실행된다:
`seo_analyst → content_writer → image_creator → seo_optimizer → blog_publisher`

## 실행 명령어

```bash
# 최초 1회: 톤앤매너 분석 (tone_samples/*.txt → tone_guide.yaml)
python analyze_tone.py

# 메인 실행
python main.py

# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치 (최초 1회)
playwright install chromium
```

## 환경 설정

`.env` 파일 필요 (`.env.example` 참고):
- `GOOGLE_API_KEY` — Gemini LLM + Imagen 4 통합 키
- `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` — 네이버 DataLab + 검색 API
- `NAVER_BLOG_ID` — 네이버 블로그 아이디

네이버 로그인: 최초 실행 시 브라우저가 열리면 수동 로그인 → `session/naver_cookies.json` 자동 저장 → 이후 자동 로그인.

## 아키텍처

### 에이전트 파이프라인 (Sequential)

| 에이전트 | 파일 | 핵심 동작 |
|---------|------|---------|
| `seo_analyst` | `config/agents.yaml` | 네이버 DataLab + 검색 API로 키워드 트렌드/경쟁 글 분석 |
| `content_writer` | `config/agents.yaml` | tone_guide.yaml 기반 평문 글 작성, `[IMAGE_N]` 마커 삽입 |
| `image_creator` | `config/agents.yaml` | Imagen 4 생성 → EXIF 주입 → SEO 파일명 변경 |
| `seo_optimizer` | `config/agents.yaml` | 마크다운 기호 완전 제거, 키워드 배치, 태그 15개 선정 |
| `blog_publisher` | `config/agents.yaml` | Playwright로 스마트에디터 ONE 블록 순차 입력 후 발행 |

### 블록 분리 입력 방식 (핵심 설계)

`main.py`의 `parse_content_blocks()`가 `[IMAGE_N]` 마커를 기준으로 `re.split()`으로 텍스트/이미지 블록 배열을 만든다.
`NaverSmartEditorTool`은 이 배열을 순서대로 입력한다:
- 텍스트 블록 → `pyperclip.copy()` → `Ctrl+V`
- 이미지 블록 → `page.expect_file_chooser()` → `set_files(경로)`

**절대 하지 말 것:**
- 이미지 경로를 클립보드에 복사 (브라우저가 로컬 파일 자동 업로드 불가)
- HTML을 클립보드에 붙여넣기 (`<h2>` 등 태그가 plain text로 노출됨)
- XML-RPC로 발행 (구버전 에디터 2.0 강제 → DIA+ 감점)
- `expect_file_chooser()` 바깥에서 이미지 버튼 클릭 (이중 클릭 → 파일탐색기 오류)

### 콘텐츠 출력 형식

`content_writer`와 `seo_optimizer` 모두 **마크다운 기호 완전 금지** (`#`, `**`, `-` 등).
오직 줄바꿈만 사용한 순수 평문(Plain Text)으로 출력해야 한다.
`[IMAGE_N]` 마커는 seo_optimizer 처리 중에도 반드시 보존된다.

### 톤앤매너

`tone_samples/*.txt`에 사용자 샘플 글을 넣고 `analyze_tone.py`를 실행하면 `tone_guide.yaml`(100~150 토큰)이 생성된다.
매 실행 시 샘플 전문 대신 이 YAML만 프롬프트에 주입한다 (토큰 약 95% 절약).

### 사주 데이터 계산

`tools/saju_data_tool.py`에서 `sajupy` 라이브러리 사용:
```python
from sajupy import calculate_saju
result = calculate_saju(year=..., month=..., day=..., hour=..., minute=...,
                        city="Seoul", use_solar_time=True)
```
`city="Seoul"`, `use_solar_time=True`로 서울 진태양시 자동 보정. LLM이 직접 명리학 데이터를 계산하지 않도록 이 툴을 경유한다.

### 이미지 생성

`tools/gemini_image_tool.py`: Imagen 4 모델 ID = `imagen-4.0-generate-001`, retry 3회.
프롬프트에 항상 추가: `"Do not include any letters, characters, hanja, korean text, numbers, words, or writing of any kind in the image."`

`tools/exif_injector_tool.py`: PNG → JPEG 변환 + 가짜 EXIF(제조사/기기/날짜) 주입 + SEO 파일명(`메인키워드_서브키워드_N.jpg`).
