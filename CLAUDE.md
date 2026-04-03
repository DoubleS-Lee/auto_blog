# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

**블로그 주제: '세상 모든 것에는 이유가 있다'**
수학을 배우는 이유, 강아지가 짖는 이유, 미분이 존재하는 이유 등 — 세상의 모든 현상과 개념에 대해 "왜 그럴까?"에 답하는 교육/정보 블로그.

네이버 블로그에 콘텐츠를 자동 생성·발행하는 시스템.
실행하면 SEO 에이전트가 인기 키워드를 추천하고, 사용자가 주제를 최종 선택한 뒤 5개 CrewAI 에이전트가 순차 실행된다:
`seo_analyst → (GUI 주제 선택) → content_writer → image_creator → seo_optimizer → blog_publisher`

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

### 실행 흐름 (2단계 실행)

```
python main.py
  ↓
[1단계] seo_analyst 실행
  → 네이버 DataLab + 검색 API로 인기 키워드 5~10개 추천 목록 생성
  ↓
[GUI 주제 선택 팝업]
  → tkinter Listbox로 추천 키워드 목록 표시
  → 사용자가 클릭 선택 또는 직접 입력
  → 최종 주제 확정
  ↓
[2단계] content_writer → image_creator → seo_optimizer → blog_publisher 순차 실행
```

### 에이전트 파이프라인

| 에이전트 | 파일 | 핵심 동작 |
|---------|------|---------|
| `seo_analyst` | `config/agents.yaml` | 네이버 DataLab + 검색 API로 키워드 트렌드/경쟁 글 분석 → 추천 주제 5~10개 출력 |
| `content_writer` | `config/agents.yaml` | tone_guide.yaml 기반 평문 글 작성, `[IMAGE_N]` 마커 삽입 |
| `image_creator` | `config/agents.yaml` | Imagen 4 생성 → EXIF 주입 → SEO 파일명 변경 |
| `seo_optimizer` | `config/agents.yaml` | 마크다운 기호 완전 제거, 키워드 배치, 태그 15개 선정 |
| `blog_publisher` | `config/agents.yaml` | Playwright로 스마트에디터 ONE 블록 순차 입력 후 발행 |

### GUI 주제 선택 + 작성 방향 입력 (`show_topic_selector()`)

`main.py`의 `show_topic_selector(topics)` 함수가 seo_analyst 결과를 받아 tkinter 팝업을 띄운다:
- 추천 키워드 Listbox (클릭 선택)
- 직접 입력 텍스트 박스 (자유 입력)
- **작성 강조 사항** 텍스트 입력 박스 — 사용자가 content_writer에게 전달할 메모 (예: "초등학생도 이해할 수 있게", "수식 없이 비유로만 설명")
- 확인 버튼 → `(주제, 강조사항)` 튜플 반환

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
- LLM에게 수식·공식·데이터 직접 계산 요청 (Hallucination 위험 — 외부 툴/검증된 출처 사용)

### 콘텐츠 출력 형식

`content_writer`와 `seo_optimizer` 모두 **마크다운 기호 완전 금지** (`#`, `**`, `-` 등).
오직 줄바꿈만 사용한 순수 평문(Plain Text)으로 출력해야 한다.
`[IMAGE_N]` 마커는 seo_optimizer 처리 중에도 반드시 보존된다.

### 톤앤매너

`tone_samples/*.txt`에 사용자 샘플 글을 넣고 `analyze_tone.py`를 실행하면 `tone_guide.yaml`(100~150 토큰)이 생성된다.
매 실행 시 샘플 전문 대신 이 YAML만 프롬프트에 주입한다 (토큰 약 95% 절약).
글쓰기 방향: "강의하듯 설명하되 친근하게", "왜? 라는 질문에서 시작", 논리적 근거 + 감성적 서술.

### 이미지 생성

`tools/gemini_image_tool.py`: Imagen 4 모델 ID = `imagen-4.0-generate-001`, retry 3회.
프롬프트에 항상 추가: `"Do not include any letters, characters, hanja, korean text, numbers, words, or writing of any kind in the image."`

이미지는 SEO 파일명(`메인키워드_서브키워드_N.jpg`)으로 저장한다. PNG → JPEG 변환만 수행한다.
