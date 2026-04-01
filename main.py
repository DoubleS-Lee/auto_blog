import re
import os
from dotenv import load_dotenv

load_dotenv()


def _parse_text_chunk(chunk: str) -> list:
    """
    텍스트 청크를 quote 블록과 일반 텍스트 블록으로 분리.
    '> 소제목' 패턴을 {"type": "quote"} 블록으로 변환.
    """
    blocks = []
    lines = chunk.split("\n")
    current_lines = []

    for line in lines:
        if line.strip().startswith("> "):
            # 쌓인 일반 텍스트 먼저 flush
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    blocks.append({"type": "text", "content": text})
                current_lines = []
            # quote 블록 추가 ('> ' 제거)
            quote_content = line.strip()[2:].strip()
            blocks.append({"type": "quote", "content": quote_content})
        else:
            current_lines.append(line)

    # 남은 일반 텍스트 flush
    if current_lines:
        text = "\n".join(current_lines).strip()
        if text:
            blocks.append({"type": "text", "content": text})

    return blocks


def parse_content_blocks(text: str, image_paths: list) -> list:
    """
    [IMAGE_N] 마커를 기준으로 텍스트를 블록 배열로 파싱.
    '> 소제목' → quote 블록, 일반 텍스트 → text 블록, 이미지 → image 블록.
    LLM에게 치환 맡기지 않고 Python re.split()으로 처리.

    반환 예:
    [
        {"type": "image", "path": "output/images/키워드_1.jpg"},
        {"type": "quote", "content": "나의 첫 사주 상담 경험"},
        {"type": "text", "content": "본문 텍스트... **굵게** 처리도 포함"},
        {"type": "image", "path": "output/images/키워드_2.jpg"},
        ...
    ]
    """
    pattern = r'\[IMAGE_(\d+)\]'
    parts = re.split(pattern, text)
    # parts = ["텍스트1", "1", "텍스트2", "2", "텍스트3", ...]

    blocks = []
    i = 0
    while i < len(parts):
        chunk = parts[i].strip()
        if chunk:
            blocks.extend(_parse_text_chunk(chunk))
        if i + 1 < len(parts):
            img_idx = int(parts[i + 1]) - 1
            if img_idx < len(image_paths):
                blocks.append({"type": "image", "path": image_paths[img_idx]})
            i += 2
        else:
            i += 1
    return blocks


def parse_image_paths_from_result(image_result: str) -> list:
    """
    image_generation_task 결과에서 이미지 경로 목록 추출.
    예: "IMAGE_1: output/images/키워드_1.jpg" → ["output/images/키워드_1.jpg", ...]
    """
    paths = []
    for line in image_result.splitlines():
        if "output/images/" in line:
            path = line.split("output/images/", 1)
            if len(path) > 1:
                full_path = "output/images/" + path[1].strip()
                paths.append(full_path)
    return paths


def parse_seo_result(seo_result: str) -> tuple:
    """
    seo_optimization_task 결과에서 title, content, tags 추출.
    """
    title = ""
    content_lines = []
    tags = ""
    in_content = False

    for line in seo_result.splitlines():
        if line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip()
        elif line.startswith("CONTENT:"):
            in_content = True
        elif line.startswith("TAGS:"):
            in_content = False
            tags = line.replace("TAGS:", "").strip()
        elif in_content:
            content_lines.append(line)

    content = "\n".join(content_lines).strip()
    return title, content, tags


def load_tone_guide() -> str:
    """tone_guide.yaml 로드 (100~150 토큰, 샘플 전문 대신 사용)"""
    try:
        with open("tone_guide.yaml", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "(톤앤매너 가이드 없음 - analyze_tone.py를 먼저 실행하세요)"


if __name__ == "__main__":
    from crew import BlogAutomationCrew

    topic = input("블로그 주제를 입력하세요: ").strip()
    if not topic:
        print("주제를 입력해야 합니다.")
        exit(1)

    answer = input("최종 발행하시겠습니까? (y=발행 / n=입력만 하고 확인) [y/n]: ").strip().lower()
    dry_run = answer != "y"

    tone_guide = load_tone_guide()
    print(f"\n[✓] 톤앤매너 가이드 로드 완료 ({len(tone_guide)}자)")
    print(f"[✓] 주제: {topic}")
    print("[→] 크루 실행 시작...\n")

    crew_instance = BlogAutomationCrew()

    # 1~4단계: 키워드 분석 → 글 작성 → 이미지 생성 → SEO 최적화
    result = crew_instance.crew().kickoff(inputs={
        "topic": topic,
        "tone_guide": tone_guide,
        "blocks": "[]",  # blog_publishing_task에서 아래에서 교체됨
    })

    # 에이전트 결과에서 데이터 추출
    tasks_output = crew_instance.crew().tasks

    image_result = ""
    seo_result = ""
    for task_out in tasks_output:
        if hasattr(task_out, "output") and task_out.output:
            name = getattr(task_out, "name", "") or ""
            raw = str(task_out.output.raw) if hasattr(task_out.output, "raw") else str(task_out.output)
            if "IMAGE_" in raw and "output/images" in raw:
                image_result = raw
            if "TITLE:" in raw and "TAGS:" in raw:
                seo_result = raw

    # 블록 파싱
    image_paths = parse_image_paths_from_result(image_result)
    title, content, tags = parse_seo_result(seo_result)

    if not content:
        print("[!] SEO 최적화 결과를 파싱하지 못했습니다. 크루 출력을 확인하세요.")
        print(result)
        exit(1)

    blocks = parse_content_blocks(content, image_paths)
    print(f"\n[✓] 블록 파싱 완료: 총 {len(blocks)}개 블록")
    print(f"[✓] 제목: {title}")
    print(f"[✓] 태그: {tags}")

    # 5단계: 블로그 발행
    from tools import NaverSmartEditorTool
    publisher = NaverSmartEditorTool()
    publish_result = publisher._run(
        title=title,
        blocks=blocks,
        tags=tags,
        dry_run=dry_run,
    )
    print(f"\n[✓] {publish_result}")
