# 사주 블로그 자동화 시스템 - 조사 내용

## 1. 프로젝트 개요

**목적:** 사주 관련 정보를 제공하는 네이버 블로그 자동화

- 개인 운세 풀이 X
- 사주 개념/지식/원리/트렌드 정보 제공 O

**콘텐츠 방향:**

- 사주 개념 설명: 천간/지지, 오행, 십성, 신살, 일주 특성 등
- 사주 상식: 궁합 보는 법, 대운 흐름, 용신 찾는 법 등
- 시즌 정보: 을사년 특징, 월별 운세 흐름, 신년 사주 트렌드 등
- 교양/입문: 사주명리학 기초, 타로와 사주 비교, 역학 상식 등

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

---

## 3. 네이버 DIA+ / C-Rank 알고리즘 분석

### DIA+(Deep Intent Analysis Plus) 핵심 평가 항목

1. **문서 품질:** 정보성, 독창성, 경험 기반 서술
2. **키워드 적합성:** 제목/본문/태그의 키워드 자연스러운 배치
3. **체류 시간:** 읽기 편한 구조, 충분한 분량 (1000~1400자)
4. **이미지 품질:** 직접 촬영한 것처럼 보이는 EXIF 정보, SEO 파일명

### C-Rank 핵심 평가 항목

1. **전문성:** 특정 주제에 집중된 블로그 (사주 정보 특화)
2. **활동성:** 꾸준한 포스팅
3. **인기도:** 공감/댓글/공유

### AI 감지 회피 전략

- 경험 기반 서술 강제: "사주를 공부하다 보면...", "실제로 상담하다 보면..."
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

### EXIF 정보 주입 (piexif + Pillow)

- 가짜 촬영 정보를 주입하여 직접 찍은 사진처럼 위장
- PNG → JPEG 변환 필수 (EXIF는 JPEG만 지원)

**주입 항목 전체:**

| 카테고리 | 항목 | 내용 |
|---------|------|------|
| 카메라 정보 | Make, Model | 제조사 + 기기명 |
| 카메라 정보 | LensModel | 렌즈 모델명 |
| 카메라 정보 | FirmwareVersion | 펌웨어 버전 |
| 카메라 정보 | Software | 카메라 앱 이름 |
| 촬영 설정 | FNumber | 조리개 값 (F1.6~F1.78) |
| 촬영 설정 | ExposureTime | 셔터스피드 (1/60~1/1000) |
| 촬영 설정 | ISOSpeedRatings | ISO 감도 (카메라별 범위 랜덤) |
| 촬영 설정 | ExposureBiasValue | 노출 보정 (0 EV) |
| 촬영 설정 | Flash | 플래시 미사용 (0) |
| 사진 속성 | FocalLength | 초점거리 |
| 사진 속성 | WhiteBalance | 자동 화이트밸런스 (0) |
| 사진 속성 | MeteringMode | 중앙 중점 측광 (2) |
| 사진 속성 | ColorSpace | sRGB (1) |
| 사진 속성 | XResolution, YResolution | 72dpi |
| 시간/장소 | DateTime, DateTimeOriginal, DateTimeDigitized | 현재 기준 1~30일 전 랜덤 |
| 시간/장소 | GPS (위도/경도/고도) | 서울 근방 랜덤 (37.5°N, 127.0°E ±0.05°) |
| 편집 이력 | Software | 카메라 앱명으로 마지막 수정 프로그램 위장 |

**랜덤 카메라 프로파일 (3종):**

| 기기 | 렌즈 | F값 | ISO 범위 |
|------|------|-----|---------|
| Samsung SM-S928B (갤럭시 S24 Ultra) | Samsung 23mm F1.7 | F1.7 | 50~3200 |
| Apple iPhone 15 Pro | back triple camera 6.765mm f/1.78 | F1.78 | 32~2500 |
| Apple iPhone 16 | back dual wide camera 4.28mm f/1.6 | F1.6 | 32~2000 |

### SEO 파일명

- 형식: `{메인키워드}_{서브키워드}_{N}.jpg`
- 예: `을사년운세_용띠운세_1.jpg`
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

### tone_guide.yaml 구조

```yaml
tone:
  opening_pattern: "경험담으로 시작"
  sentence_length: "짧고 끊어 읽기 쉽게, 2~3줄마다 줄바꿈"
  vocabulary: "한자 용어는 괄호로 풀이 (예: 일주(日柱))"
  avoid:
    - "AI 번역투 표현"
    - "게다가/또한/더불어 반복"
  signature_phrases:
    - "솔직히 말씀드리면"
    - "실제로 상담하다 보면"
```

---

## 7. 사주 데이터 Hallucination 방지

### 문제

- LLM이 천간/지지/십성 등 명리학 데이터를 직접 계산하면 오류 가능성 높음

### 해결책: SajuDataTool

- 로컬 명리학 DB(JSON/CSV) 또는 만세력 API 조회
- 에이전트는 조회된 정확한 데이터를 바탕으로 글쓰기만 담당
- 사용 시점: 특정 개념(일주/신살/천간 등) 설명 글에서만 선택적 사용

### 만세력 라이브러리: sajupy

- 설치: `pip install sajupy`
- 1900~2100년 만세력 데이터 내장
- `city="Seoul"` + `use_solar_time=True` 설정 시 서울 경도(126.978°) 기준 진태양시 자동 보정
- 별도 32분 보정 로직 불필요

```python
from sajupy import calculate_saju

result = calculate_saju(
    year=1990, month=10, day=10,
    hour=14, minute=30,
    city="Seoul",
    use_solar_time=True
)
```

---

## 8. 마크다운 노출 문제 분석

### 문제

- LLM이 `## 소제목`, `**강조**` 등 마크다운으로 글을 작성
- 네이버 스마트에디터 ONE은 마크다운 렌더링 안 함
- 클립보드 붙여넣기 시 `##`, `**` 기호가 그대로 화면에 노출

### 해결책 (이중 방어)

1. **content_writer 지시:** 처음부터 마크다운 기호 절대 사용 금지
2. **seo_optimizer 역할:** 잔존 마크다운 기호 완전 제거 후 평문 출력

---

## 9. 필요한 API 키 정리

| 키 이름               | 용도                  | 비고              |
| --------------------- | --------------------- | ----------------- |
| `GOOGLE_API_KEY`      | Gemini LLM + Imagen 4 | 통합 키           |
| `NAVER_CLIENT_ID`     | DataLab + 검색 API    | 네이버 개발자센터 |
| `NAVER_CLIENT_SECRET` | DataLab + 검색 API    | 네이버 개발자센터 |
| `NAVER_BLOG_ID`       | 블로그 포스팅 URL     | 블로그 아이디     |

---

## 10. 라이브러리 조사

| 라이브러리              | 용도                       |
| ----------------------- | -------------------------- |
| `crewai[tools]`         | 멀티에이전트 프레임워크    |
| `google-genai`          | Gemini LLM + Imagen 4      |
| `playwright`            | 스마트에디터 ONE 자동화    |
| `pyperclip`             | 텍스트 클립보드 붙여넣기   |
| `pillow`                | 이미지 처리 (PNG→JPG 변환) |
| `piexif`                | EXIF 정보 주입             |
| `korean-lunar-calendar` | 만세력 계산 (선택)         |
| `python-dotenv`         | .env 파일 로드             |
| `requests`              | 네이버 API 호출            |
