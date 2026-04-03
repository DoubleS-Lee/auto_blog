# Why 블로그 자동화 시스템 - 조사 내용

## 1. 프로젝트 개요

**블로그 주제: '세상 모든 것에는 이유가 있다'**

- 개인 의견/주장 X
- 현상·개념·원리에 대한 '왜?'의 해답과 사유 제공 O

**콘텐츠 방향:**

- 학문적 이유: 수학을 배우는 이유, 미분이 존재하는 이유, 생물을 배우는 이유 등
- 자연/생물 현상: 강아지가 짖는 이유, 하늘이 파란 이유, 사람이 하품하는 이유 등
- 사회/문화 현상: 악수를 하는 이유, 교복을 입는 이유, 줄을 서는 이유 등
- 일상의 궁금증: 커피가 쓴 이유, 눈물이 짠 이유, 잠을 자야 하는 이유 등

**타깃 독자:**

- 호기심 많은 일반인, 학생, 직장인
- "왜?" 라고 물어본 적 있지만 깊이 파고든 적 없는 사람

---

## 2. 기술 스택 조사

### 2-1. LLM: Google Gemini 3.1 Flash Lite

- 모든 에이전트의 LLM으로 사용
- 비용 효율적, 빠른 응답
- 한국어 지원 우수

### 2-2. 이미지 생성: Google Imagen 4

- 모델 ID: `imagen-4.0-generate-001`
- SDK: `google-genai` 패키지 (`from google import genai`)
- 호출 방식:
  ```python
  client = genai.Client(api_key=GOOGLE_API_KEY)
  response = client.models.generate_images(
      model="imagen-4.0-generate-001",
      prompt=prompt,
      config=types.GenerateImagesConfig(
          number_of_images=1,
          aspect_ratio="1:1",
          safety_filter_level="BLOCK_ONLY_HIGH",
      )
  )
  ```
- 이미지 저장: `response.generated_images[0].image.save(path)`
- 주의: 프롬프트에 텍스트 금지 조건 명시 필수
  - "Do not include any letters, characters, hanja, korean text, numbers, words, or writing of any kind in the image."

### 2-3. 멀티에이전트 프레임워크: CrewAI

- 5개 에이전트, Sequential Process
- 각 에이전트는 전문 역할과 도구 보유
- `config/agents.yaml`, `config/tasks.yaml`로 에이전트/태스크 정의
- LLM 설정: `LLM(model="gemini/gemini-3.1-flash-lite")`

### 2-4. 네이버 블로그 자동화: Playwright

- XML-RPC 방식 사용 불가 (구버전 스마트에디터 2.0 강제 → DIA+ 감점)
- Playwright로 스마트에디터 ONE 직접 조작
- 세션쿠키 자동로그인 (`session/naver_cookies.json`)

### 2-5. 네이버 API

- **DataLab API (무료):** 키워드 트렌드 분석
  - 엔드포인트: `https://openapi.naver.com/v1/datalab/search`
  - 헤더: `X-Naver-Client-Id`, `X-Naver-Client-Secret`
- **검색 API (무료):** 블로그 검색으로 경쟁 글 분석
  - 엔드포인트: `https://openapi.naver.com/v1/search/blog`

### 2-6. GUI: tkinter

- Python 기본 내장 라이브러리 (별도 설치 불필요)
- 추천 주제 선택 팝업: Listbox + Entry + Button
- SEO 에이전트 결과를 파싱하여 추천 목록 구성
- **작성 강조 사항 입력**: 사용자가 content_writer에게 전달할 추가 지시 텍스트 박스
  - 예: "초등학생도 이해할 수 있게", "수식 없이 비유로만 설명", "역사적 배경도 포함"
  - 입력값은 content_writing_task 프롬프트에 직접 주입됨

---

## 3. 네이버 DIA+ / C-Rank 알고리즘 분석

### DIA+(Deep Intent Analysis Plus) 핵심 평가 항목

1. **문서 품질:** 정보성, 독창성, 경험 기반 서술
2. **키워드 적합성:** 제목/본문/태그의 키워드 자연스러운 배치
3. **체류 시간:** 읽기 편한 구조, 충분한 분량 (2000~3000자)
4. **이미지 품질:** 직접 촬영한 것처럼 보이는 EXIF 정보, SEO 파일명

### C-Rank 핵심 평가 항목

1. **전문성:** 특정 주제에 집중된 블로그 ('이유/원리' 정보 특화)
2. **활동성:** 꾸준한 포스팅
3. **인기도:** 공감/댓글/공유

### SEO 전략: 의문형 키워드 특성

'왜 그럴까?' 계열 검색어의 특징:

- 검색 의도: 정보 탐색(Informational) — 광고/상품 의도 없음 → 경쟁 낮음
- 대표 패턴: `[주제] + 이유`, `왜 + [현상]`, `[개념] + 원리`, `[행동] + 하는 이유`
- 예시: "수학 배우는 이유", "강아지 짖는 이유", "미분 왜 배워", "하품 이유"
- 네이버 검색 의도 분류: 정보성 검색 — 블로그 노출 비중 높음

### AI 감지 회피 전략

- 경험/사유 기반 서술 강제: "생각해보면...", "실제로 알고 보면...", "흥미롭게도..."
- 톤앤매너 가이드 (`tone_guide.yaml`) 기반 글쓰기 — 사용자 샘플 글에서 학습한 고유 문체 주입
- 마크다운 기호 완전 금지 → 순수 평문(Plain Text) 출력
- 패턴 회피는 페르소나 다변화가 아닌 **글 주제/소재 다변화**로 대응

> 랜덤 페르소나 제거 이유: 사용자 본인 글에서 학습한 톤앤매너와 외부 페르소나 캐릭터가 충돌하여 어색한 글 생성 위험. 톤앤매너 단독 사용이 일관성 면에서 더 우수.

---

## 4. 스마트에디터 ONE 자동화 조사

### 블록 분리 입력 방식 (핵심 설계)

기존에 시도했다가 실패한 방식들:

- ❌ XML-RPC: 구버전 에디터 2.0 강제 적용
- ❌ HTML 클립보드 붙여넣기: `<h2>`, `<img>` 태그가 plain text로 그대로 입력됨
- ❌ 이미지 경로 클립보드: 브라우저가 로컬 파일 자동 업로드 안 함

채택한 방식 (블록 분리 순차 입력):

```
텍스트 블록 → pyperclip.copy() → Ctrl+V
이미지 블록 → expect_file_chooser() → set_files(경로)
```

- 텍스트/이미지를 블록 단위로 분리하여 순서대로 입력
- `[IMAGE_N]` 마커를 기준으로 Python `re.split()`으로 파싱

### file_chooser 사용 시 주의사항

```python
# 올바른 방법 (클릭 1회)
with page.expect_file_chooser() as fc_info:
    page.click(".se-toolbar-item-image")
file_chooser = fc_info.value
file_chooser.set_files(path)

# 잘못된 방법 (이중 클릭 → 파일탐색기 오류)
page.click(".se-toolbar-item-image")  # 중복 클릭 금지
with page.expect_file_chooser() as fc_info:
    page.click(".se-toolbar-item-image")
```

---

## 5. 이미지 처리 조사

### 이미지 저장 (Pillow)

- PNG → JPEG 변환 (Pillow)
- EXIF 주입 없이 순수 이미지만 저장

### SEO 파일명

- 형식: `{메인키워드}_{서브키워드}_{N}.jpg`
- 예: `수학배우는이유_미분원리_1.jpg`
- 공백은 하이픈(-)으로 대체

---

## 6. 토큰 최적화 조사

### 문제

- 매번 tone_samples/ 전체(2000~3000 토큰)를 프롬프트에 주입하면 비용 낭비

### 해결책: 최초 1회 분석 → 압축 YAML 가이드

```
[최초 1회] python analyze_tone.py
→ tone_samples/*.txt → Gemini 분석 → tone_guide.yaml (100~150 토큰)

[매 실행] tone_guide.yaml만 프롬프트에 주입
→ 토큰 약 95% 절약
```

### tone_guide.yaml 구조 (Why 블로그 특화)

```yaml
tone:
  opening_pattern: "왜? 라는 질문으로 시작 후 핵심 답변 선제시"
  sentence_length: "짧고 끊어 읽기 쉽게, 2~3줄마다 줄바꿈"
  vocabulary: "전문 용어는 괄호로 쉽게 풀이 (예: 미분(순간변화율))"
  avoid:
    - "AI 번역투 표현"
    - "게다가/또한/더불어 반복"
    - "결론적으로/정리하자면 남발"
  signature_phrases:
    - "생각해보면"
    - "실제로 알고 보면"
    - "흥미롭게도"
```

---

## 7. 마크다운 노출 문제 분석

### 문제

- LLM이 `## 소제목`, `**강조**` 등 마크다운으로 글을 작성
- 네이버 스마트에디터 ONE은 마크다운 렌더링 안 함
- 클립보드 붙여넣기 시 `##`, `**` 기호가 그대로 화면에 노출

### 해결책 (이중 방어)

1. **content_writer 지시:** 처음부터 마크다운 기호 절대 사용 금지
2. **seo_optimizer 역할:** 잔존 마크다운 기호 완전 제거 후 평문 출력

---

## 8. 필요한 API 키 정리

| 키 이름               | 용도                  | 비고              |
| --------------------- | --------------------- | ----------------- |
| `GOOGLE_API_KEY`      | Gemini LLM + Imagen 4 | 통합 키           |
| `NAVER_CLIENT_ID`     | DataLab + 검색 API    | 네이버 개발자센터 |
| `NAVER_CLIENT_SECRET` | DataLab + 검색 API    | 네이버 개발자센터 |
| `NAVER_BLOG_ID`       | 블로그 포스팅 URL     | 블로그 아이디     |

---

## 9. 라이브러리 조사

| 라이브러리      | 용도                       |
| --------------- | -------------------------- |
| `crewai[tools]` | 멀티에이전트 프레임워크    |
| `google-genai`  | Gemini LLM + Imagen 4      |
| `playwright`    | 스마트에디터 ONE 자동화    |
| `pyperclip`     | 텍스트 클립보드 붙여넣기   |
| `pillow`        | 이미지 처리 (PNG→JPG 변환) |
| `python-dotenv` | .env 파일 로드             |
| `requests`      | 네이버 API 호출            |
| `pyyaml`        | YAML 파싱                  |
| `tkinter`       | GUI 주제 선택 팝업 (내장)  |
