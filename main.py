import re
import os
import tkinter as tk
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────
# 텍스트/블록 파싱 유틸
# ─────────────────────────────────────────────

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
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    blocks.append({"type": "text", "content": text})
                current_lines = []
            quote_content = line.strip()[2:].strip()
            blocks.append({"type": "quote", "content": quote_content})
        else:
            current_lines.append(line)

    if current_lines:
        text = "\n".join(current_lines).strip()
        if text:
            blocks.append({"type": "text", "content": text})

    return blocks


def parse_content_blocks(text: str, image_paths: list) -> list:
    """
    [IMAGE_N] 마커를 기준으로 텍스트를 블록 배열로 파싱.
    '> 소제목' → quote 블록, 일반 텍스트 → text 블록, 이미지 → image 블록.
    """
    pattern = r'\[IMAGE_(\d+)\]'
    parts = re.split(pattern, text)

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
    """image_generation_task 결과에서 이미지 경로 목록 추출."""
    paths = []
    for line in image_result.splitlines():
        if "output/images/" in line:
            path = line.split("output/images/", 1)
            if len(path) > 1:
                full_path = "output/images/" + path[1].strip()
                paths.append(full_path)
    return paths


def parse_seo_result(seo_result: str) -> tuple:
    """seo_optimization_task 결과에서 title, content, tags 추출."""
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


def parse_recommended_topics(seo_result: str) -> list:
    """
    keyword_research_task 결과에서 추천 주제 목록 추출.
    여러 출력 패턴을 순서대로 시도한다:
      1) RECOMMENDED_TOPICS: 주제1 | 주제2 | ...  (파이프 구분, 한 줄)
      2) RECOMMENDED_TOPICS: 아래 여러 줄 (번호 목록 또는 - 목록)
      3) 추천 주제: 로 시작하는 한국어 레이블
    """
    lines = seo_result.splitlines()

    # 패턴 1·3: 한 줄 파이프 구분 (RECOMMENDED_TOPICS: 또는 추천 주제:)
    keywords = ("RECOMMENDED_TOPICS:", "추천 주제:", "추천주제:")
    for i, line in enumerate(lines):
        upper = line.strip()
        for kw in keywords:
            if upper.upper().startswith(kw.upper()):
                raw = upper[len(kw):].strip()
                if "|" in raw:
                    topics = [_clean_topic(t) for t in raw.split("|") if t.strip()]
                    if topics:
                        return topics
                # 파이프 없으면 아래 줄을 목록으로 파싱
                subsequent = []
                for j in range(i + 1, min(i + 10, len(lines))):
                    t = _clean_topic(lines[j])
                    if t:
                        subsequent.append(t)
                    elif subsequent:  # 빈 줄이 나오면 종료
                        break
                if subsequent:
                    return subsequent

    return []


def _clean_topic(text: str) -> str:
    """번호·기호 접두사 제거 후 괄호 내용 정리."""
    import re
    t = text.strip()
    # "1. " "1) " "- " "* " 등 제거
    t = re.sub(r'^[\d]+[.)]\s*', '', t)
    t = re.sub(r'^[-*•]\s*', '', t)
    # 앞뒤 괄호 제거: (주제) → 주제
    t = re.sub(r'^\((.+)\)$', r'\1', t)
    return t.strip()


def load_tone_guide() -> str:
    """tone_guide.yaml 로드 (100~150 토큰, 샘플 전문 대신 사용)"""
    try:
        with open("tone_guide.yaml", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "(톤앤매너 가이드 없음 - analyze_tone.py를 먼저 실행하세요)"


# ─────────────────────────────────────────────
# GUI: 주제 선택 + 작성 강조 사항 입력
# ─────────────────────────────────────────────

def show_topic_selector(topics: list) -> dict:
    """
    SEO 에이전트 추천 주제를 GUI 팝업으로 선택.
    직접 입력 + 작성 강조 사항 입력도 허용.
    반환: {"topic": 선택된 주제, "emphasis": 강조 사항 (없으면 "")}
    """
    PLACEHOLDER = "예: 초등학생도 이해할 수 있게, 수식 없이 비유로만 설명"
    result = {"topic": None, "emphasis": ""}

    root = tk.Tk()
    root.title("블로그 주제 선택")
    root.geometry("460x500")
    root.resizable(False, False)

    tk.Label(root, text="추천 주제를 선택하거나 직접 입력하세요", font=("맑은 고딕", 11, "bold")).pack(pady=(14, 6))

    frame = tk.Frame(root)
    frame.pack(fill=tk.BOTH, padx=20)

    scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
    listbox = tk.Listbox(frame, height=8, font=("맑은 고딕", 10),
                         yscrollcommand=scrollbar.set, selectmode=tk.SINGLE)
    scrollbar.config(command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    for t in topics:
        listbox.insert(tk.END, t)

    tk.Label(root, text="또는 직접 입력:", font=("맑은 고딕", 10)).pack(anchor="w", padx=20, pady=(10, 2))
    topic_entry = tk.Entry(root, font=("맑은 고딕", 10), width=50)
    topic_entry.pack(padx=20)

    tk.Label(root, text="작성 강조 사항 (content_writer에게 전달, 선택):",
             font=("맑은 고딕", 10)).pack(anchor="w", padx=20, pady=(14, 2))
    emphasis_entry = tk.Entry(root, font=("맑은 고딕", 10), width=50, fg="grey")
    emphasis_entry.insert(0, PLACEHOLDER)
    emphasis_entry.pack(padx=20)

    def _on_emphasis_focus_in(e):
        if emphasis_entry.get() == PLACEHOLDER:
            emphasis_entry.delete(0, tk.END)
            emphasis_entry.config(fg="black")

    def _on_emphasis_focus_out(e):
        if not emphasis_entry.get().strip():
            emphasis_entry.insert(0, PLACEHOLDER)
            emphasis_entry.config(fg="grey")

    emphasis_entry.bind("<FocusIn>", _on_emphasis_focus_in)
    emphasis_entry.bind("<FocusOut>", _on_emphasis_focus_out)

    def on_confirm():
        topic = topic_entry.get().strip()
        if not topic and listbox.curselection():
            topic = topics[listbox.curselection()[0]]
        em = emphasis_entry.get().strip()
        if em == PLACEHOLDER:
            em = ""
        result["topic"] = topic or None
        result["emphasis"] = em
        root.destroy()

    tk.Button(root, text="확인", command=on_confirm,
              font=("맑은 고딕", 11), width=12).pack(pady=18)

    root.mainloop()
    return result


# ─────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from crew import BlogAutomationCrew

    answer = input("최종 발행하시겠습니까? (y=발행 / n=입력만 하고 확인) [y/n]: ").strip().lower()
    dry_run = answer != "y"

    tone_guide = load_tone_guide()
    print(f"\n[✓] 톤앤매너 가이드 로드 완료 ({len(tone_guide)}자)")

    crew_instance = BlogAutomationCrew()

    # ── 1단계: SEO 분석 + 추천 주제 생성 ──────────────────
    print("[→] 1단계: SEO 키워드 분석 중...\n")
    seo_result_obj = crew_instance.seo_crew().kickoff(inputs={"topic": "세상 모든 이유"})
    seo_raw = str(seo_result_obj.raw) if hasattr(seo_result_obj, "raw") else str(seo_result_obj)

    recommended_topics = parse_recommended_topics(seo_raw)
    if not recommended_topics:
        # RECOMMENDED_TOPICS가 없으면 기본 안내
        print("[!] 추천 주제를 파싱하지 못했습니다. 직접 입력해 주세요.")

    # ── GUI: 주제 선택 + 강조 사항 입력 ──────────────────
    selection = show_topic_selector(recommended_topics)

    if not selection["topic"]:
        print("주제가 선택되지 않았습니다. 종료합니다.")
        exit(1)

    topic = selection["topic"]
    emphasis = selection["emphasis"]

    print(f"\n[✓] 주제: {topic}")
    if emphasis:
        print(f"[✓] 강조 사항: {emphasis}")
    print("[→] 2단계: 글 작성 → 이미지 생성 → SEO 최적화 시작...\n")

    # ── 2단계: 글 작성 → 이미지 생성 → SEO 최적화 ────────
    content_result_obj = crew_instance.content_crew().kickoff(inputs={
        "topic": topic,
        "tone_guide": tone_guide,
        "emphasis": emphasis,
        "seo_analysis": seo_raw,
        "blocks": "[]",
    })

    # 에이전트 결과에서 데이터 추출
    tasks_output = crew_instance.content_crew().tasks

    image_result = ""
    seo_result = ""
    for task_out in tasks_output:
        if hasattr(task_out, "output") and task_out.output:
            raw = str(task_out.output.raw) if hasattr(task_out.output, "raw") else str(task_out.output)
            if "output/images" in raw:
                image_result = raw
            if "TITLE:" in raw and "TAGS:" in raw:
                seo_result = raw

    # 블록 파싱
    image_paths = parse_image_paths_from_result(image_result)
    title, content, tags = parse_seo_result(seo_result)

    if not content:
        print("[!] SEO 최적화 결과를 파싱하지 못했습니다. 크루 출력을 확인하세요.")
        print(content_result_obj)
        exit(1)

    blocks = parse_content_blocks(content, image_paths)
    print(f"\n[✓] 블록 파싱 완료: 총 {len(blocks)}개 블록")
    print(f"[✓] 제목: {title}")
    print(f"[✓] 태그: {tags}")

    # ── 5단계: 블로그 발행 ────────────────────────────────
    from tools import NaverSmartEditorTool
    publisher = NaverSmartEditorTool()
    publish_result = publisher._run(
        title=title,
        blocks=blocks,
        tags=tags,
        dry_run=dry_run,
    )
    print(f"\n[✓] {publish_result}")
