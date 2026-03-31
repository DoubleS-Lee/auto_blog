"""
톤앤매너 분석 스크립트 (최초 1회 실행)

tone_samples/*.txt 파일들을 읽어 Gemini로 분석 후
tone_guide.yaml (100~150 토큰)을 생성한다.

샘플 글 추가/수정 시 재실행하면 tone_guide.yaml이 갱신된다.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def analyze_tone():
    sample_dir = Path("tone_samples")
    if not sample_dir.exists():
        print("[!] tone_samples/ 폴더가 없습니다. 폴더를 만들고 샘플 글을 넣어주세요.")
        return

    sample_files = list(sample_dir.glob("*.txt"))
    if not sample_files:
        print("[!] tone_samples/ 폴더에 .txt 파일이 없습니다.")
        return

    samples = [f.read_text(encoding="utf-8") for f in sample_files]
    combined = "\n\n---\n\n".join(samples)
    print(f"[✓] 샘플 {len(samples)}개 로드 완료 (총 {len(combined)}자)")

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[!] GOOGLE_API_KEY 환경변수가 없습니다.")
        return

    try:
        from google import genai
    except ImportError:
        print("[!] google-genai가 설치되지 않았습니다. pip install google-genai")
        return

    client = genai.Client(api_key=api_key)

    prompt = f"""다음 블로그 글 샘플들의 문체와 톤을 분석하여
100~150 토큰 이내의 YAML 스타일 가이드로 압축하라.

출력 형식 (YAML만 출력, 설명 없이):
tone:
  opening_pattern: "(서론 시작 패턴)"
  sentence_length: "(문장 길이/리듬)"
  vocabulary: "(어휘 특징)"
  avoid:
    - "(피해야 할 표현 1)"
    - "(피해야 할 표현 2)"
  signature_phrases:
    - "(자주 쓰는 표현 1)"
    - "(자주 쓰는 표현 2)"

샘플:
{combined}"""

    print("[→] Gemini로 톤 분석 중...")
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=prompt,
    )

    output = response.text.strip()
    if output.startswith("```yaml"):
        output = output[7:]
    if output.startswith("```"):
        output = output[3:]
    if output.endswith("```"):
        output = output[:-3]
    output = output.strip()

    with open("tone_guide.yaml", "w", encoding="utf-8") as f:
        f.write(output)

    print(f"[✓] tone_guide.yaml 생성 완료 ({len(output)}자)")
    print("\n--- 생성된 톤 가이드 ---")
    print(output)


if __name__ == "__main__":
    analyze_tone()
