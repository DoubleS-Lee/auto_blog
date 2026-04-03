"""
Why 블로그 자동화 GUI
실행: python gui.py
"""
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from dotenv import load_dotenv

load_dotenv()


class TextRedirector:
    """print() 출력을 GUI 로그창으로 리다이렉트."""
    def __init__(self, widget: scrolledtext.ScrolledText):
        self.widget = widget

    def write(self, text: str):
        self.widget.after(0, self._append, text)

    def _append(self, text: str):
        self.widget.configure(state="normal")
        self.widget.insert(tk.END, text)
        self.widget.see(tk.END)
        self.widget.configure(state="disabled")

    def flush(self):
        pass

    def isatty(self):
        return False


class BlogAutomationGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Why 블로그 자동화 — 세상 모든 것에는 이유가 있다")
        self.root.resizable(True, True)

        self._seo_raw = ""          # seo_crew 결과 저장
        self._recommended: list = []

        self._build_ui()

    # ─────────────────────────────────────────────
    # UI 구성
    # ─────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # ── 1단계: SEO 분석 버튼 ──────────────────────
        step1_frame = ttk.LabelFrame(self.root, text="1단계: SEO 분석", padding=8)
        step1_frame.pack(fill="x", **pad)

        self.seo_btn = ttk.Button(step1_frame, text="SEO 분석 시작", command=self._start_seo)
        self.seo_btn.pack(side="left", fill="x", expand=True)

        self.login_btn = ttk.Button(
            step1_frame, text="네이버 재로그인", command=self._start_login, width=18
        )
        self.login_btn.pack(side="right", padx=(8, 0))

        # ── 2단계: 주제 선택 + 설정 ───────────────────
        step2_frame = ttk.LabelFrame(self.root, text="2단계: 주제 선택 및 글 작성", padding=8)
        step2_frame.pack(fill="x", **pad)

        # 추천 주제 Listbox
        ttk.Label(step2_frame, text="추천 주제 (SEO 분석 후 자동 채워짐):").pack(anchor="w")
        list_frame = ttk.Frame(step2_frame)
        list_frame.pack(fill="x", pady=(2, 6))

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.topic_listbox = tk.Listbox(
            list_frame, height=5, font=("맑은 고딕", 10),
            yscrollcommand=scrollbar.set, selectmode=tk.SINGLE,
            activestyle="dotbox",
        )
        scrollbar.config(command=self.topic_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.topic_listbox.pack(side="left", fill="x", expand=True)
        self.topic_listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        # 직접 입력
        ttk.Label(step2_frame, text="직접 입력 (Listbox 선택을 덮어씀):").pack(anchor="w", pady=(4, 0))
        self.topic_var = tk.StringVar()
        ttk.Entry(step2_frame, textvariable=self.topic_var, font=("맑은 고딕", 11)).pack(
            fill="x", pady=(2, 6)
        )

        # 강조 사항
        EMPHASIS_PLACEHOLDER = "예: 초등학생도 이해할 수 있게, 수식 없이 비유로만 설명"
        ttk.Label(step2_frame, text="작성 강조 사항 (content_writer에게 전달, 선택):").pack(anchor="w")
        self.emphasis_var = tk.StringVar(value=EMPHASIS_PLACEHOLDER)
        self.emphasis_entry = ttk.Entry(
            step2_frame, textvariable=self.emphasis_var,
            font=("맑은 고딕", 10), foreground="grey",
        )
        self.emphasis_entry.pack(fill="x", pady=(2, 6))
        self.emphasis_entry.bind("<FocusIn>",  lambda e: self._clear_placeholder(EMPHASIS_PLACEHOLDER))
        self.emphasis_entry.bind("<FocusOut>", lambda e: self._restore_placeholder(EMPHASIS_PLACEHOLDER))

        # 발행 옵션 + 실행 버튼
        bottom_frame = ttk.Frame(step2_frame)
        bottom_frame.pack(fill="x", pady=(4, 0))

        self.publish_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            bottom_frame,
            text="완료 후 최종 발행 (해제 시 태그 입력까지만)",
            variable=self.publish_var,
        ).pack(side="left")

        self.write_btn = ttk.Button(
            bottom_frame, text="글 작성 + 발행",
            command=self._start_content, state="disabled",
        )
        self.write_btn.pack(side="right")

        # ── 로그 창 ───────────────────────────────────
        log_frame = ttk.LabelFrame(self.root, text="실행 로그", padding=8)
        log_frame.pack(fill="both", expand=True, **pad)

        self.log_box = scrolledtext.ScrolledText(
            log_frame,
            state="disabled",
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            wrap="word",
        )
        self.log_box.pack(fill="both", expand=True)

        # stdout/stderr 리다이렉트
        redirector = TextRedirector(self.log_box)
        sys.stdout = redirector
        sys.stderr = redirector

        self.root.update_idletasks()
        self.root.minsize(660, 620)

    # ─────────────────────────────────────────────
    # Placeholder 헬퍼
    # ─────────────────────────────────────────────

    def _clear_placeholder(self, placeholder: str):
        if self.emphasis_var.get() == placeholder:
            self.emphasis_var.set("")
            self.emphasis_entry.configure(foreground="black")

    def _restore_placeholder(self, placeholder: str):
        if not self.emphasis_var.get().strip():
            self.emphasis_var.set(placeholder)
            self.emphasis_entry.configure(foreground="grey")

    def _on_listbox_select(self, _event):
        """Listbox 클릭 시 직접 입력 필드를 선택 항목으로 채움."""
        sel = self.topic_listbox.curselection()
        if sel:
            self.topic_var.set(self._recommended[sel[0]])

    # ─────────────────────────────────────────────
    # 버튼 상태
    # ─────────────────────────────────────────────

    def _set_seo_running(self, running: bool):
        self.root.after(0, lambda: self.seo_btn.configure(
            state="disabled" if running else "normal",
            text="분석 중..." if running else "SEO 분석 시작",
        ))

    def _set_content_running(self, running: bool):
        self.root.after(0, lambda: self.write_btn.configure(
            state="disabled",
            text="작성 중..." if running else "글 작성 + 발행",
        ))
        if not running:
            self.root.after(0, lambda: self.write_btn.configure(state="normal"))

    # ─────────────────────────────────────────────
    # 네이버 재로그인
    # ─────────────────────────────────────────────

    def _start_login(self):
        self.login_btn.configure(state="disabled", text="로그인 중...")
        threading.Thread(target=self._run_login, daemon=True).start()

    def _run_login(self):
        try:
            import os
            from playwright.sync_api import sync_playwright

            PROFILE_DIR = os.path.abspath("session/chrome_profile")
            print("[→] 네이버 로그인 브라우저를 엽니다...")

            with sync_playwright() as p:
                os.makedirs(PROFILE_DIR, exist_ok=True)
                context = p.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                page = context.new_page()
                page.goto("https://nid.naver.com/nidlogin.login")
                print("[!] 브라우저에서 로그인 후 잠시 기다려 주세요. 자동으로 감지합니다.")
                try:
                    page.wait_for_url("https://www.naver.com/**", timeout=300_000)
                except Exception:
                    pass
                page.wait_for_timeout(1500)
                context.close()

            print("[✓] 로그인 완료 — 프로파일 저장됨 (다음 실행부터 자동 로그인)")

        except Exception as e:
            import traceback
            print(f"\n[오류] 로그인 실패: {e}")
            print(traceback.format_exc())
        finally:
            self.root.after(0, lambda: self.login_btn.configure(
                state="normal", text="네이버 재로그인"
            ))

    # ─────────────────────────────────────────────
    # 1단계: SEO 분석
    # ─────────────────────────────────────────────

    def _start_seo(self):
        self._set_seo_running(True)
        threading.Thread(target=self._run_seo, daemon=True).start()

    def _run_seo(self):
        try:
            from main import parse_recommended_topics, load_tone_guide
            from crew import BlogAutomationCrew

            print("[→] 1단계: SEO 키워드 분석 중...\n")
            crew_instance = BlogAutomationCrew()
            result_obj = crew_instance.seo_crew().kickoff(inputs={"topic": "세상 모든 이유"})
            self._seo_raw = str(result_obj.raw) if hasattr(result_obj, "raw") else str(result_obj)

            self._recommended = parse_recommended_topics(self._seo_raw)

            if self._recommended:
                self.root.after(0, self._populate_topics)
                print(f"\n[✓] 추천 주제 {len(self._recommended)}개 확인 — 주제를 선택 후 '글 작성 + 발행'을 눌러 주세요.")
            else:
                print("\n[!] 추천 주제를 파싱하지 못했습니다. 직접 입력 후 진행해 주세요.")
                print("─── SEO 에이전트 원문 출력 (마지막 500자) ───")
                print(self._seo_raw[-500:] if len(self._seo_raw) > 500 else self._seo_raw)
                print("────────────────────────────────────────────")
                self.root.after(0, lambda: self.write_btn.configure(state="normal"))

        except Exception as e:
            import traceback
            print(f"\n[오류] SEO 분석 실패: {e}")
            print(traceback.format_exc())
        finally:
            self._set_seo_running(False)

    def _populate_topics(self):
        """추천 주제를 Listbox에 채우고 2단계 버튼 활성화."""
        self.topic_listbox.delete(0, tk.END)
        for t in self._recommended:
            self.topic_listbox.insert(tk.END, t)
        self.write_btn.configure(state="normal")

    # ─────────────────────────────────────────────
    # 2단계: 글 작성 + 발행
    # ─────────────────────────────────────────────

    def _start_content(self):
        EMPHASIS_PLACEHOLDER = "예: 초등학생도 이해할 수 있게, 수식 없이 비유로만 설명"

        topic = self.topic_var.get().strip()
        if not topic:
            print("[!] 주제를 선택하거나 직접 입력해 주세요.")
            return

        emphasis = self.emphasis_var.get().strip()
        if emphasis == EMPHASIS_PLACEHOLDER:
            emphasis = ""

        self._set_content_running(True)
        threading.Thread(
            target=self._run_content,
            args=(topic, emphasis),
            daemon=True,
        ).start()

    def _run_content(self, topic: str, emphasis: str):
        try:
            from main import (
                parse_content_blocks,
                parse_image_paths_from_result,
                parse_seo_result,
                load_tone_guide,
            )
            from crew import BlogAutomationCrew
            from tools import NaverSmartEditorTool

            dry_run = not self.publish_var.get()
            tone_guide = load_tone_guide()

            print(f"[✓] 톤앤매너 가이드 로드 완료 ({len(tone_guide)}자)")
            print(f"[✓] 주제: {topic}")
            if emphasis:
                print(f"[✓] 강조 사항: {emphasis}")
            print(f"[✓] 최종 발행: {'예' if not dry_run else '아니오 (태그 입력까지만)'}")
            print("[→] 2단계: 글 작성 → 이미지 생성 → SEO 최적화 시작...\n")

            crew_instance = BlogAutomationCrew()
            result_obj = crew_instance.content_crew().kickoff(inputs={
                "topic": topic,
                "tone_guide": tone_guide,
                "emphasis": emphasis,
                "seo_analysis": self._seo_raw,
                "blocks": "[]",
            })

            # 결과 파싱
            image_result = ""
            seo_result = ""
            for task_out in crew_instance.content_crew().tasks:
                if hasattr(task_out, "output") and task_out.output:
                    raw = str(task_out.output.raw) if hasattr(task_out.output, "raw") else str(task_out.output)
                    if "output/images" in raw:
                        image_result = raw
                    if "TITLE:" in raw and "TAGS:" in raw:
                        seo_result = raw

            image_paths = parse_image_paths_from_result(image_result)
            title, content, tags = parse_seo_result(seo_result)

            if not content:
                print("[!] SEO 최적화 결과를 파싱하지 못했습니다.")
                print(str(result_obj))
                return

            blocks = parse_content_blocks(content, image_paths)
            print(f"\n[✓] 블록 파싱 완료: 총 {len(blocks)}개 블록")
            print(f"[✓] 제목: {title}")
            print(f"[✓] 태그: {tags}")

            publisher = NaverSmartEditorTool()
            publish_result = publisher._run(
                title=title,
                blocks=blocks,
                tags=tags,
                dry_run=dry_run,
            )
            print(f"\n[✓] {publish_result}")

        except Exception as e:
            import traceback
            print(f"\n[오류] {e}")
            print(traceback.format_exc())
        finally:
            self._set_content_running(False)


if __name__ == "__main__":
    root = tk.Tk()
    app = BlogAutomationGUI(root)
    root.mainloop()
