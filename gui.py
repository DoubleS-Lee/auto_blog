"""
Why 블로그 자동화 GUI
실행: python gui.py

흐름:
  1단계: 키워드 발굴 방법 선택 → 키워드 목록 표시
  2단계: 키워드 선택 → 블로그 주제 5개 생성
  3단계: 주제 선택 → 글 작성 + 발행
"""
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from dotenv import load_dotenv

load_dotenv()

# 뉴스 카테고리 목록 (NaverNewsTrendTool과 동기화)
NEWS_CATEGORIES = ["IT", "경제", "건강", "교육", "여행", "생활", "육아", "시사"]

EMPHASIS_PLACEHOLDER = "예: 초등학생도 이해할 수 있게, 수식 없이 비유로만 설명"


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

        self._keywords: list = []   # 발굴된 키워드 목록
        self._topics: list = []     # 생성된 주제 목록
        self._seo_raw: str = ""     # 마지막 SEO 분석 원문 (content_crew용)

        self._build_ui()

    # ─────────────────────────────────────────────
    # UI 구성
    # ─────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # ── 1단계: 키워드 발굴 방법 선택 ──────────────
        step1 = ttk.LabelFrame(self.root, text="1단계: 키워드 발굴 방법 선택", padding=8)
        step1.pack(fill="x", **pad)

        self._method_var = tk.IntVar(value=2)  # 기본: 쇼핑 트렌드

        ttk.Radiobutton(
            step1, text="다음(Daum) 실시간 트렌드",
            variable=self._method_var, value=1,
            command=self._on_method_change,
        ).grid(row=0, column=0, sticky="w", pady=2)

        ttk.Radiobutton(
            step1, text="네이버 쇼핑 트렌드",
            variable=self._method_var, value=2,
            command=self._on_method_change,
        ).grid(row=1, column=0, sticky="w", pady=2)

        method3_frame = ttk.Frame(step1)
        method3_frame.grid(row=2, column=0, sticky="w", pady=2)

        ttk.Radiobutton(
            method3_frame, text="네이버 뉴스 분석  카테고리:",
            variable=self._method_var, value=3,
            command=self._on_method_change,
        ).pack(side="left")

        self._category_var = tk.StringVar(value="IT")
        self._category_combo = ttk.Combobox(
            method3_frame,
            textvariable=self._category_var,
            values=NEWS_CATEGORIES,
            width=8,
            state="disabled",
        )
        self._category_combo.pack(side="left", padx=(4, 0))

        btn_row = ttk.Frame(step1)
        btn_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self._discover_btn = ttk.Button(
            btn_row, text="키워드 발굴 시작", command=self._start_discover
        )
        self._discover_btn.pack(side="left", fill="x", expand=True)

        self._login_btn = ttk.Button(
            btn_row, text="네이버 재로그인", command=self._start_login, width=18
        )
        self._login_btn.pack(side="right", padx=(8, 0))

        # ── 2단계: 키워드 선택 → 주제 생성 ──────────
        step2 = ttk.LabelFrame(self.root, text="2단계: 키워드 선택 → 주제 5개 생성", padding=8)
        step2.pack(fill="x", **pad)

        ttk.Label(step2, text="발굴된 키워드 (클릭해서 선택):").pack(anchor="w")
        kw_frame = ttk.Frame(step2)
        kw_frame.pack(fill="x", pady=(2, 4))

        kw_scroll = ttk.Scrollbar(kw_frame, orient=tk.VERTICAL)
        self._kw_listbox = tk.Listbox(
            kw_frame, height=5, font=("맑은 고딕", 10),
            yscrollcommand=kw_scroll.set, selectmode=tk.SINGLE,
            activestyle="dotbox",
        )
        kw_scroll.config(command=self._kw_listbox.yview)
        kw_scroll.pack(side="right", fill="y")
        self._kw_listbox.pack(side="left", fill="x", expand=True)
        self._kw_listbox.bind("<<ListboxSelect>>", self._on_kw_select)

        ttk.Label(step2, text="또는 직접 입력:").pack(anchor="w", pady=(4, 0))
        self._kw_var = tk.StringVar()
        ttk.Entry(step2, textvariable=self._kw_var, font=("맑은 고딕", 11)).pack(
            fill="x", pady=(2, 6)
        )

        self._gen_topic_btn = ttk.Button(
            step2, text="이 키워드로 주제 5개 생성",
            command=self._start_gen_topics, state="disabled",
        )
        self._gen_topic_btn.pack(fill="x")

        # ── 3단계: 주제 선택 → 글 작성 ───────────────
        step3 = ttk.LabelFrame(self.root, text="3단계: 주제 선택 → 글 작성 + 발행", padding=8)
        step3.pack(fill="x", **pad)

        ttk.Label(step3, text="생성된 주제 (클릭해서 선택):").pack(anchor="w")
        topic_frame = ttk.Frame(step3)
        topic_frame.pack(fill="x", pady=(2, 4))

        topic_scroll = ttk.Scrollbar(topic_frame, orient=tk.VERTICAL)
        self._topic_listbox = tk.Listbox(
            topic_frame, height=5, font=("맑은 고딕", 10),
            yscrollcommand=topic_scroll.set, selectmode=tk.SINGLE,
            activestyle="dotbox",
        )
        topic_scroll.config(command=self._topic_listbox.yview)
        topic_scroll.pack(side="right", fill="y")
        self._topic_listbox.pack(side="left", fill="x", expand=True)
        self._topic_listbox.bind("<<ListboxSelect>>", self._on_topic_select)

        ttk.Label(step3, text="또는 직접 입력:").pack(anchor="w", pady=(4, 0))
        self._topic_var = tk.StringVar()
        ttk.Entry(step3, textvariable=self._topic_var, font=("맑은 고딕", 11)).pack(
            fill="x", pady=(2, 4)
        )

        ttk.Label(step3, text="작성 강조 사항 (선택, content_writer에게 전달):").pack(anchor="w")
        self._emphasis_var = tk.StringVar(value=EMPHASIS_PLACEHOLDER)
        self._emphasis_entry = ttk.Entry(
            step3, textvariable=self._emphasis_var,
            font=("맑은 고딕", 10), foreground="grey",
        )
        self._emphasis_entry.pack(fill="x", pady=(2, 6))
        self._emphasis_entry.bind("<FocusIn>",  lambda e: self._clear_ph())
        self._emphasis_entry.bind("<FocusOut>", lambda e: self._restore_ph())

        write_row = ttk.Frame(step3)
        write_row.pack(fill="x")

        self._publish_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            write_row,
            text="완료 후 최종 발행 (해제 시 태그 입력까지만)",
            variable=self._publish_var,
        ).pack(side="left")

        self._write_btn = ttk.Button(
            write_row, text="글 작성 + 발행",
            command=self._start_content, state="disabled",
        )
        self._write_btn.pack(side="right")

        # ── 로그 창 ───────────────────────────────────
        log_frame = ttk.LabelFrame(self.root, text="실행 로그", padding=8)
        log_frame.pack(fill="both", expand=True, **pad)

        self._log_box = scrolledtext.ScrolledText(
            log_frame, state="disabled", font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white", wrap="word",
        )
        self._log_box.pack(fill="both", expand=True)

        redirector = TextRedirector(self._log_box)
        sys.stdout = redirector
        sys.stderr = redirector

        self.root.update_idletasks()
        self.root.minsize(680, 780)

    # ─────────────────────────────────────────────
    # 헬퍼
    # ─────────────────────────────────────────────

    def _on_method_change(self):
        state = "readonly" if self._method_var.get() == 3 else "disabled"
        self._category_combo.configure(state=state)

    def _on_kw_select(self, _event):
        sel = self._kw_listbox.curselection()
        if sel:
            self._kw_var.set(self._keywords[sel[0]])

    def _on_topic_select(self, _event):
        sel = self._topic_listbox.curselection()
        if sel:
            self._topic_var.set(self._topics[sel[0]])

    def _clear_ph(self):
        if self._emphasis_var.get() == EMPHASIS_PLACEHOLDER:
            self._emphasis_var.set("")
            self._emphasis_entry.configure(foreground="black")

    def _restore_ph(self):
        if not self._emphasis_var.get().strip():
            self._emphasis_var.set(EMPHASIS_PLACEHOLDER)
            self._emphasis_entry.configure(foreground="grey")

    def _set_btn(self, btn: ttk.Button, running: bool, idle_text: str):
        self.root.after(0, lambda: btn.configure(
            state="disabled",
            text="실행 중..." if running else idle_text,
        ))
        if not running:
            self.root.after(0, lambda: btn.configure(state="normal"))

    # ─────────────────────────────────────────────
    # 네이버 재로그인
    # ─────────────────────────────────────────────

    def _start_login(self):
        self._login_btn.configure(state="disabled", text="로그인 중...")
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
                print("[!] 브라우저에서 로그인 후 잠시 기다려 주세요.")
                try:
                    page.wait_for_url("https://www.naver.com/**", timeout=300_000)
                except Exception:
                    pass
                page.wait_for_timeout(1500)
                context.close()

            print("[✓] 로그인 완료 — 프로파일 저장됨")
        except Exception as e:
            import traceback
            print(f"\n[오류] 로그인 실패: {e}")
            print(traceback.format_exc())
        finally:
            self.root.after(0, lambda: self._login_btn.configure(
                state="normal", text="네이버 재로그인"
            ))

    # ─────────────────────────────────────────────
    # 1단계: 키워드 발굴
    # ─────────────────────────────────────────────

    def _start_discover(self):
        self._discover_btn.configure(state="disabled", text="발굴 중...")
        method = self._method_var.get()
        category = self._category_var.get() if method == 3 else None
        threading.Thread(
            target=self._run_discover, args=(method, category), daemon=True
        ).start()

    def _run_discover(self, method: int, category: str | None):
        try:
            from main import parse_keyword_list

            method_names = {1: "다음 실시간 트렌드", 2: "네이버 쇼핑 트렌드", 3: f"네이버 뉴스 ({category})"}
            print(f"\n[→] 1단계: 키워드 발굴 시작 — {method_names[method]}\n")

            if method == 1:
                from tools import DaumTrendTool
                result = DaumTrendTool()._run(max_keywords=20)

            elif method == 2:
                from tools import NaverShoppingInsightTool
                result = NaverShoppingInsightTool()._run(
                    period_days=30, top_categories=5, keywords_per_category=8
                )

            else:  # method == 3
                from tools import NaverNewsTrendTool
                result = NaverNewsTrendTool()._run(
                    category=category, count=80, top_keywords=20
                )

            print(result)
            print()

            keywords = parse_keyword_list(result)

            if keywords:
                self._keywords = keywords
                self.root.after(0, self._populate_keywords)
                print(f"[✓] 키워드 {len(keywords)}개 발굴 완료 — 키워드를 선택하세요.")
            else:
                print("[!] 키워드를 파싱하지 못했습니다. 직접 입력 후 진행하세요.")
                self.root.after(0, lambda: self._gen_topic_btn.configure(state="normal"))

        except Exception as e:
            import traceback
            print(f"\n[오류] 키워드 발굴 실패: {e}")
            print(traceback.format_exc())
        finally:
            self.root.after(0, lambda: self._discover_btn.configure(
                state="normal", text="키워드 발굴 시작"
            ))

    def _populate_keywords(self):
        self._kw_listbox.delete(0, tk.END)
        for kw in self._keywords:
            self._kw_listbox.insert(tk.END, kw)
        self._gen_topic_btn.configure(state="normal")

    # ─────────────────────────────────────────────
    # 2단계: 주제 5개 생성
    # ─────────────────────────────────────────────

    def _start_gen_topics(self):
        keyword = self._kw_var.get().strip()
        if not keyword:
            print("[!] 키워드를 선택하거나 직접 입력해 주세요.")
            return
        self._gen_topic_btn.configure(state="disabled", text="주제 생성 중...")
        threading.Thread(target=self._run_gen_topics, args=(keyword,), daemon=True).start()

    def _run_gen_topics(self, keyword: str):
        try:
            from main import parse_topics
            from crew import BlogAutomationCrew

            print(f"\n[→] 2단계: '{keyword}' 키워드로 주제 5개 생성 중...\n")
            crew_instance = BlogAutomationCrew()
            result_obj = crew_instance.topic_crew().kickoff(inputs={"keyword": keyword})
            raw = str(result_obj.raw) if hasattr(result_obj, "raw") else str(result_obj)
            self._seo_raw = raw  # content_crew context용

            topics = parse_topics(raw)

            if topics:
                self._topics = topics
                self.root.after(0, self._populate_topics)
                print(f"\n[✓] 주제 {len(topics)}개 생성 완료 — 주제를 선택하세요.")
            else:
                print("\n[!] 주제를 파싱하지 못했습니다. 직접 입력 후 진행하세요.")
                print("─── 에이전트 원문 출력 (마지막 500자) ───")
                print(raw[-500:] if len(raw) > 500 else raw)
                print("──────────────────────────────────────")
                self.root.after(0, lambda: self._write_btn.configure(state="normal"))

        except Exception as e:
            import traceback
            print(f"\n[오류] 주제 생성 실패: {e}")
            print(traceback.format_exc())
        finally:
            self.root.after(0, lambda: self._gen_topic_btn.configure(
                state="normal", text="이 키워드로 주제 5개 생성"
            ))

    def _populate_topics(self):
        self._topic_listbox.delete(0, tk.END)
        for t in self._topics:
            self._topic_listbox.insert(tk.END, t)
        self._write_btn.configure(state="normal")

    # ─────────────────────────────────────────────
    # 3단계: 글 작성 + 발행
    # ─────────────────────────────────────────────

    def _start_content(self):
        topic = self._topic_var.get().strip()
        if not topic:
            print("[!] 주제를 선택하거나 직접 입력해 주세요.")
            return

        emphasis = self._emphasis_var.get().strip()
        if emphasis == EMPHASIS_PLACEHOLDER:
            emphasis = ""

        self._write_btn.configure(state="disabled", text="작성 중...")
        threading.Thread(
            target=self._run_content, args=(topic, emphasis), daemon=True
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

            dry_run = not self._publish_var.get()
            tone_guide = load_tone_guide()

            print(f"[✓] 톤앤매너 가이드 로드 완료 ({len(tone_guide)}자)")
            print(f"[✓] 주제: {topic}")
            if emphasis:
                print(f"[✓] 강조 사항: {emphasis}")
            print(f"[✓] 최종 발행: {'예' if not dry_run else '아니오 (태그 입력까지만)'}")
            print("[→] 3단계: 글 작성 → 이미지 생성 → SEO 최적화 시작...\n")

            crew_instance = BlogAutomationCrew()
            crew_instance.content_crew().kickoff(inputs={
                "topic": topic,
                "tone_guide": tone_guide,
                "emphasis": emphasis,
                "seo_analysis": self._seo_raw,
                "blocks": "[]",
            })

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
                return

            blocks = parse_content_blocks(content, image_paths)
            print(f"\n[✓] 블록 파싱 완료: 총 {len(blocks)}개 블록")
            print(f"[✓] 제목: {title}")
            print(f"[✓] 태그: {tags}")

            publisher = NaverSmartEditorTool()
            publish_result = publisher._run(
                title=title, blocks=blocks, tags=tags, dry_run=dry_run,
            )
            print(f"\n[✓] {publish_result}")

        except Exception as e:
            import traceback
            print(f"\n[오류] {e}")
            print(traceback.format_exc())
        finally:
            self.root.after(0, lambda: self._write_btn.configure(
                state="normal", text="글 작성 + 발행"
            ))


if __name__ == "__main__":
    root = tk.Tk()
    app = BlogAutomationGUI(root)
    root.mainloop()
