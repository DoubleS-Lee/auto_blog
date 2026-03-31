# 사주 블로그 자동화 시스템 - 구현 계획

## 시스템 구조

```
주제 입력
  ↓
[Agent 1] seo_analyst      → 네이버 키워드 트렌드 + 경쟁 글 분석
  ↓
[Agent 2] content_writer   → 사주 정보 글 작성 (평문 + [IMAGE_N] 마커)
  ↓
[Agent 3] image_creator    → Imagen 4 생성 + EXIF 주입 + SEO 파일명
  ↓
[Agent 4] seo_optimizer    → 마크다운 제거 + 키워드 배치 + 태그 선정
  ↓
[main.py] 블록 파싱        → [IMAGE_N] 기준으로 텍스트/이미지 블록 배열 생성
  ↓
[Agent 5] blog_publisher   → Playwright 스마트에디터 ONE 순차 입력 + 발행
```

---

## 파일 구조

```
d:\00.Google CLI\260330_auto_blog\
├── research.md
├── plan.md
├── main.py
├── crew.py
├── analyze_tone.py
├── .env
├── .env.example
├── requirements.txt
├── tone_guide.yaml              # analyze_tone.py 실행 후 자동 생성
├── tone_samples/
│   ├── sample_1.txt             # 사용자 작성 샘플 글
│   └── sample_2.txt
├── config/
│   ├── agents.yaml
│   └── tasks.yaml
├── tools/
│   ├── __init__.py
│   ├── naver_datalab_tool.py
│   ├── naver_search_tool.py
│   ├── saju_data_tool.py
│   ├── gemini_image_tool.py
│   ├── exif_injector_tool.py
│   └── naver_smart_editor_tool.py
├── session/
│   └── naver_cookies.json       # 최초 로그인 후 자동 생성
└── output/
    ├── images/
    └── published_result.md
```

---

## 에이전트 설계

| #   | 에이전트         | 역할                                              | 툴                                |
| --- | ---------------- | ------------------------------------------------- | --------------------------------- |
| 1   | `seo_analyst`    | 네이버 키워드 트렌드 분석, 경쟁 글 분석           | NaverDataLabTool, NaverSearchTool |
| 2   | `content_writer` | 사주 정보 글 작성 (평문, 경험 기반, AI 느낌 없이) | SajuDataTool (선택적)             |
| 3   | `image_creator`  | Imagen 4 이미지 생성 + EXIF 주입 + SEO 파일명     | GeminiImageTool, ExifInjectorTool |
| 4   | `seo_optimizer`  | 마크다운 완전 제거 + 키워드 배치 + 태그 선정      | (LLM만)                           |
| 5   | `blog_publisher` | Playwright 스마트에디터 ONE 자동 게시             | NaverSmartEditorTool              |

---

## 구현 순서

### Step 1. 환경 설정

- `requirements.txt`
- `.env.example`
- `tools/__init__.py`

### Step 2. 네이버 API 툴

- `tools/naver_datalab_tool.py` — 키워드 트렌드 분석
- `tools/naver_search_tool.py` — 경쟁 블로그 검색

### Step 3. 사주 데이터 툴

- `tools/saju_data_tool.py` — 명리학 개념 DB 조회 (Hallucination 방지)
  - 라이브러리: `sajupy` — `city="Seoul"`, `use_solar_time=True`로 진태양시 자동 보정

### Step 4. 이미지 툴

- `tools/gemini_image_tool.py` — Imagen 4 생성 (retry 3회)
- `tools/exif_injector_tool.py` — EXIF 주입 + SEO 파일명 변경

### Step 5. 발행 툴

- `tools/naver_smart_editor_tool.py` — Playwright 블록 분리 입력

### Step 6. CrewAI 설정

- `config/agents.yaml`
- `config/tasks.yaml`

### Step 7. 크루 + 진입점

- `crew.py` — 5 에이전트 Sequential 크루
- `main.py` — 블록 파싱 + 크루 실행
- `analyze_tone.py` — 톤앤매너 1회 분석

---

## 핵심 구현 상세

### [main.py] 블록 파싱 로직

```python
import re

def parse_content_blocks(text: str, image_paths: list) -> list:
    pattern = r'\[IMAGE_(\d+)\]'
    parts = re.split(pattern, text)
    # ["텍스트1", "1", "텍스트2", "2", "텍스트3"]

    blocks = []
    i = 0
    while i < len(parts):
        chunk = parts[i].strip()
        if chunk:
            blocks.append({"type": "text", "content": chunk})
        if i + 1 < len(parts):
            img_idx = int(parts[i + 1]) - 1
            if img_idx < len(image_paths):
                blocks.append({"type": "image", "path": image_paths[img_idx]})
            i += 2
        else:
            i += 1
    return blocks
```

### [naver_smart_editor_tool.py] 블록 순차 입력

```python
for block in blocks:
    if block["type"] == "text":
        pyperclip.copy(block["content"])
        page.keyboard.press("Control+v")
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)

    elif block["type"] == "image":
        # 클릭 1회만 (이중 클릭 금지)
        with page.expect_file_chooser() as fc_info:
            page.click(".se-toolbar-item-image")
        file_chooser = fc_info.value
        file_chooser.set_files(block["path"])
        page.wait_for_timeout(3000)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
```

### [config/tasks.yaml] content_writing_task 핵심 지시

- 마크다운 기호(#, ##, \*\*, \_\_, -, >) 절대 사용 금지
- 경험 기반 서술 필수: "사주를 공부하다 보면...", "실제로 상담하다 보면..."
- [IMAGE_N] 마커 삽입 위치: 서론 후 [IMAGE_1], 각 소제목 아래 [IMAGE_2]~[IMAGE_4]
- 분량: 1000~1400자

### [config/tasks.yaml] seo_optimization_task 핵심 지시

- 마크다운 기호 완전 제거 (1순위)
- [IMAGE_N] 마커 절대 보존
- 최종 결과물: 오직 줄바꿈만 사용한 평문(Plain Text)
- 출력 형식: title / content / tags

### [tone_guide.yaml] 톤앤매너 가이드 (사용자 글에서 학습)

- `analyze_tone.py` 최초 1회 실행 → `tone_guide.yaml` 생성
- 매 실행 시 `content_writer` 프롬프트에 주입 (100~150 토큰)
- 패턴 회피는 페르소나 변경이 아닌 글 주제/소재 다변화로 대응

---

## 주의사항 (설계 결정 이유)

| 항목                      | 결정                                     | 이유                                         |
| ------------------------- | ---------------------------------------- | -------------------------------------------- |
| XML-RPC 사용 금지         | Playwright 브라우저 자동화               | XML-RPC는 구버전 에디터 2.0 강제 → DIA+ 감점 |
| HTML 클립보드 금지        | 평문 텍스트만 클립보드 사용              | HTML 태그가 plain text로 그대로 노출됨       |
| 이미지 경로 클립보드 금지 | file_chooser.set_files() 사용            | 브라우저가 로컬 파일 자동 업로드 불가        |
| file_chooser 클릭 1회     | expect_file_chooser() 안에서만 클릭      | 이중 클릭 시 파일탐색기 오류                 |
| 마크다운 이중 방어        | content_writer 금지 + seo_optimizer 제거 | LLM이 마크다운 습관적으로 사용               |
| 톤가이드 YAML 분리        | analyze_tone.py 1회 실행                 | 매번 샘플 전문 주입 시 토큰 낭비 (95% 절약)  |
| SajuDataTool              | 명리학 DB 조회, LLM 계산 금지            | LLM 직접 계산 시 Hallucination 위험          |

---

## 검증 방법

1. `python analyze_tone.py` → `tone_guide.yaml` 생성 확인
2. `python main.py` → "을사년 용띠 운세" 입력
3. Agent 1 결과: 키워드 트렌드 보고서 출력 확인
4. Agent 2 결과: [IMAGE_N] 마커 + 마크다운 없는 평문 확인
5. Agent 3 결과: `을사년운세_용띠운세_1.jpg` SEO 파일명 + EXIF 확인
6. Agent 4 결과: 마크다운 완전 제거 + [IMAGE_N] 보존 + 태그 15개 확인
7. main.py 블록 파싱: `[{"type":"text",...}, {"type":"image",...}, ...]` 배열 확인
8. Agent 5: Playwright 브라우저 오픈 → 스마트에디터 ONE 자동 입력 → 발행 확인
9. 네이버 블로그에서 이미지 중간중간 삽입된 글 정상 발행 확인
