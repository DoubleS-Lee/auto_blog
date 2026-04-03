# Why 블로그 자동화 시스템 - 구현 계획

## 시스템 구조

```
python main.py
  ↓
[Agent 1] seo_analyst      → 네이버 키워드 트렌드(교육, 학문 분야) + 경쟁 글 분석 → 추천 주제 5~10개 출력
  ↓
[GUI] show_topic_selector() → tkinter 팝업: 추천 목록 Listbox + 직접 입력 → 주제 확정
  ↓
[Agent 2] content_writer   → Why 블로그 글 작성 (평문 + [IMAGE_N] 마커)
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
d:\00.Google CLI\260401_auto_blog_DoubleS\
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

| #   | 에이전트         | 역할                                                                            | 툴                                |
| --- | ---------------- | ------------------------------------------------------------------------------- | --------------------------------- |
| 1   | `seo_analyst`    | 네이버 키워드 트렌드 분석(교육, 학문 분야), 경쟁 글 분석, 추천 주제 5~10개 출력 | NaverDataLabTool, NaverSearchTool |
| 2   | `content_writer` | Why 블로그 글 작성 (평문, 논리적 서술, AI 느낌 없이)                            | (LLM만)                           |
| 3   | `image_creator`  | Imagen 4 이미지 생성 + PNG→JPEG 변환 + SEO 파일명                               | GeminiImageTool                   |
| 4   | `seo_optimizer`  | 마크다운 완전 제거 + 키워드 배치 + 태그 선정                                    | (LLM만)                           |
| 5   | `blog_publisher` | Playwright 스마트에디터 ONE 자동 게시                                           | NaverSmartEditorTool              |

---

## 구현 순서

### Step 1. 환경 설정

- `requirements.txt`
- `.env.example`
- `tools/__init__.py`

### Step 2. 네이버 API 툴

- `tools/naver_datalab_tool.py` — 키워드 트렌드 분석
- `tools/naver_search_tool.py` — 경쟁 블로그 검색

### Step 3. 이미지 툴

- `tools/gemini_image_tool.py` — Imagen 4 생성 (retry 3회), PNG→JPEG 변환, SEO 파일명 저장

### Step 4. 발행 툴

- `tools/naver_smart_editor_tool.py` — Playwright 블록 분리 입력

### Step 5. CrewAI 설정

- `config/agents.yaml`
- `config/tasks.yaml`

### Step 6. 크루 + 진입점

- `crew.py` — 5 에이전트 Sequential 크루
- `main.py` — GUI 주제 선택 + 블록 파싱 + 크루 실행
- `analyze_tone.py` — 톤앤매너 1회 분석

---

## 핵심 구현 상세

### [main.py] GUI 주제 선택 (`show_topic_selector`)

반환값: `{"topic": str, "emphasis": str}` 딕셔너리

```python
import tkinter as tk

def show_topic_selector(topics: list[str]) -> dict:
    """SEO 에이전트 추천 주제를 GUI 팝업으로 선택.
    직접 입력 + 작성 강조 사항 입력도 허용.
    반환: {"topic": 선택된 주제, "emphasis": 강조 사항 (없으면 "")}
    """
    result = {"topic": None, "emphasis": ""}

    root = tk.Tk()
    root.title("주제 선택")
    root.geometry("440x460")

    tk.Label(root, text="추천 주제를 선택하거나 직접 입력하세요", font=("맑은 고딕", 11)).pack(pady=10)

    listbox = tk.Listbox(root, height=8, font=("맑은 고딕", 10))
    for t in topics:
        listbox.insert(tk.END, t)
    listbox.pack(fill=tk.X, padx=20)

    tk.Label(root, text="또는 직접 입력:").pack(pady=(10, 2))
    topic_entry = tk.Entry(root, font=("맑은 고딕", 10), width=45)
    topic_entry.pack(padx=20)

    tk.Label(root, text="작성 강조 사항 (선택, content_writer에게 전달):").pack(pady=(14, 2))
    emphasis_entry = tk.Entry(root, font=("맑은 고딕", 10), width=45)
    emphasis_entry.insert(0, "예: 초등학생도 이해할 수 있게, 수식 없이 비유로만 설명")
    emphasis_entry.config(fg="grey")
    def clear_placeholder(e):
        if emphasis_entry.get().startswith("예:"):
            emphasis_entry.delete(0, tk.END)
            emphasis_entry.config(fg="black")
    emphasis_entry.bind("<FocusIn>", clear_placeholder)
    emphasis_entry.pack(padx=20)

    def on_confirm():
        t = topic_entry.get().strip()
        if not t and listbox.curselection():
            t = topics[listbox.curselection()[0]]
        em = emphasis_entry.get().strip()
        if em.startswith("예:"):
            em = ""
        result["topic"] = t or None
        result["emphasis"] = em
        root.destroy()

    tk.Button(root, text="확인", command=on_confirm, width=10).pack(pady=15)
    root.mainloop()
    return result
```

### [main.py] 2단계 실행 흐름

```python
# 1단계: SEO 분석 + 추천 주제 생성
seo_result = run_seo_agent()
recommended_topics = parse_recommended_topics(seo_result)

# GUI 주제 선택 + 강조 사항 입력
selection = show_topic_selector(recommended_topics)
if not selection["topic"]:
    print("주제가 선택되지 않았습니다. 종료합니다.")
    exit()

topic = selection["topic"]
emphasis = selection["emphasis"]  # content_writing_task 프롬프트에 주입

# 2단계: 선택된 주제 + 강조 사항으로 나머지 에이전트 실행
result = run_content_crew(topic, seo_result, emphasis)
```

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

### [config/tasks.yaml] seo_analyst_task 핵심 지시 (추가)

- 분석 결과 마지막에 **추천 주제 목록** 출력 필수
- 형식: `RECOMMENDED_TOPICS: 주제1 | 주제2 | 주제3 | ...`
- 주제는 블로그 테마('세상 모든 것에는 이유가 있다')에 맞는 의문형/이유형 키워드

### [config/tasks.yaml] content_writing_task 핵심 지시

- 마크다운 기호(#, ##, \*\*, \_\_, -, >) 절대 사용 금지
- "왜?" 질문으로 시작하는 논리적 구조
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
- 방향: "강의하듯 설명하되 친근하게", "왜?로 시작해 논리적 근거 제시"

---

## 주의사항 (설계 결정 이유)

| 항목                      | 결정                                     | 이유                                          |
| ------------------------- | ---------------------------------------- | --------------------------------------------- |
| XML-RPC 사용 금지         | Playwright 브라우저 자동화               | XML-RPC는 구버전 에디터 2.0 강제 → DIA+ 감점  |
| HTML 클립보드 금지        | 평문 텍스트만 클립보드 사용              | HTML 태그가 plain text로 그대로 노출됨        |
| 이미지 경로 클립보드 금지 | file_chooser.set_files() 사용            | 브라우저가 로컬 파일 자동 업로드 불가         |
| file_chooser 클릭 1회     | expect_file_chooser() 안에서만 클릭      | 이중 클릭 시 파일탐색기 오류                  |
| 마크다운 이중 방어        | content_writer 금지 + seo_optimizer 제거 | LLM이 마크다운 습관적으로 사용                |
| 톤가이드 YAML 분리        | analyze_tone.py 1회 실행                 | 매번 샘플 전문 주입 시 토큰 낭비 (95% 절약)   |
| GUI 주제 선택 + 강조 입력 | tkinter Listbox + 직접입력 + 강조사항 Entry | SEO 추천 활용 + 사용자 결정권 + 방향 전달 가능 |
| SajuDataTool 제거         | Why 블로그에 불필요                         | 새 주제 도메인과 무관                          |
| ExifInjectorTool 제거     | PNG→JPEG 변환만 수행                        | EXIF 주입 불필요                               |

---

## 검증 방법

1. `python analyze_tone.py` → `tone_guide.yaml` 생성 확인
2. `python main.py` 실행
3. Agent 1 결과: 키워드 트렌드 보고서 + 추천 주제 목록(`RECOMMENDED_TOPICS:`) 출력 확인
4. GUI 팝업: tkinter 창 표시 → 추천 목록 Listbox 확인 → 선택 또는 직접 입력 → 강조 사항 입력 → 확인
5. Agent 2 결과: [IMAGE_N] 마커 + 마크다운 없는 평문 + Why 논리구조 + 강조 사항 반영 확인
6. Agent 3 결과: `수학배우는이유_미분원리_1.jpg` SEO 파일명 확인
7. Agent 4 결과: 마크다운 완전 제거 + [IMAGE_N] 보존 + 태그 15개 확인
8. main.py 블록 파싱: `[{"type":"text",...}, {"type":"image",...}, ...]` 배열 확인
9. Agent 5: Playwright 브라우저 오픈 → 스마트에디터 ONE 자동 입력 → 발행 확인
10. 네이버 블로그에서 이미지 중간중간 삽입된 글 정상 발행 확인
