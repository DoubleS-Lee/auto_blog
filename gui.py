"""
사주 블로그 자동화 GUI
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
        self.root.title("사주 블로그 자동화")
        self.root.resizable(True, True)
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # ── 주제 입력 ──
        topic_frame = ttk.LabelFrame(self.root, text="블로그 주제", padding=8)
        topic_frame.pack(fill="x", **pad)

        self.topic_var = tk.StringVar()
        topic_entry = ttk.Entry(topic_frame, textvariable=self.topic_var, font=("맑은 고딕", 12))
        topic_entry.pack(fill="x")
        topic_entry.bind("<Return>", lambda e: self._start())

        # ── 옵션 ──
        option_frame = ttk.Frame(self.root)
        option_frame.pack(fill="x", padx=12, pady=2)

        self.publish_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            option_frame,
            text="완료 후 최종 발행 (체크 해제 시 태그 입력까지만 진행)",
            variable=self.publish_var,
        ).pack(side="left")

        # ── 버튼 행 ──
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=12, pady=6)

        self.run_btn = ttk.Button(btn_frame, text="실행", command=self._start)
        self.run_btn.pack(side="left", fill="x", expand=True)

        self.login_btn = ttk.Button(btn_frame, text="네이버 재로그인", command=self._start_login, width=18)
        self.login_btn.pack(side="right", padx=(8, 0))

        # ── 로그 ──
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

        # 최소 크기
        self.root.update_idletasks()
        self.root.minsize(640, 500)

    def _log(self, msg: str):
        self.log_box.after(0, lambda: (
            self.log_box.configure(state="normal"),
            self.log_box.insert(tk.END, msg + "\n"),
            self.log_box.see(tk.END),
            self.log_box.configure(state="disabled"),
        ))

    def _set_running(self, running: bool):
        self.root.after(0, lambda: self.run_btn.configure(
            state="disabled" if running else "normal",
            text="실행 중..." if running else "실행",
        ))

    def _start_login(self):
        self.login_btn.configure(state="disabled", text="로그인 중...")
        thread = threading.Thread(target=self._run_login, daemon=True)
        thread.start()

    def _run_login(self):
        try:
            import os, json
            from playwright.sync_api import sync_playwright

            COOKIE_PATH = "session/naver_cookies.json"
            print("[→] 네이버 로그인 브라우저를 엽니다...")

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto("https://nid.naver.com/nidlogin.login")

                print("[!] 브라우저에서 로그인 후 잠시 기다려 주세요. 자동으로 감지합니다.")

                # 로그인 완료 감지: 네이버 메인(www.naver.com)으로 이동될 때까지 대기
                try:
                    page.wait_for_url("https://www.naver.com/**", timeout=300_000)
                except Exception:
                    # 타임아웃 시 현재 쿠키라도 저장
                    pass

                # 추가 대기 (쿠키 세팅 완료)
                page.wait_for_timeout(1500)

                cookies = context.cookies()
                os.makedirs("session", exist_ok=True)
                with open(COOKIE_PATH, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)

                browser.close()

            print(f"[✓] 쿠키 저장 완료 → {COOKIE_PATH}")

        except Exception as e:
            import traceback
            print(f"\n[오류] 로그인 실패: {e}")
            print(traceback.format_exc())
        finally:
            self.root.after(0, lambda: self.login_btn.configure(state="normal", text="네이버 재로그인"))

    def _start(self):
        topic = self.topic_var.get().strip()
        if not topic:
            self._log("[!] 주제를 입력해 주세요.")
            return
        self._set_running(True)
        thread = threading.Thread(target=self._run_pipeline, args=(topic,), daemon=True)
        thread.start()

    def _run_pipeline(self, topic: str):
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
            print(f"[✓] 최종 발행: {'예' if not dry_run else '아니오 (태그 입력까지만)'}")
            print("[→] 크루 실행 시작...\n")

            crew_instance = BlogAutomationCrew()
            result = crew_instance.crew().kickoff(inputs={
                "topic": topic,
                "tone_guide": tone_guide,
                "blocks": "[]",
            })

            # 결과 파싱
            image_result = ""
            seo_result = ""
            for task_out in crew_instance.crew().tasks:
                if hasattr(task_out, "output") and task_out.output:
                    raw = str(task_out.output.raw) if hasattr(task_out.output, "raw") else str(task_out.output)
                    if "IMAGE_" in raw and "output/images" in raw:
                        image_result = raw
                    if "TITLE:" in raw and "TAGS:" in raw:
                        seo_result = raw

            image_paths = parse_image_paths_from_result(image_result)
            title, content, tags = parse_seo_result(seo_result)

            if not content:
                print("[!] SEO 최적화 결과를 파싱하지 못했습니다.")
                print(str(result))
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
            self._set_running(False)


if __name__ == "__main__":
    root = tk.Tk()
    app = BlogAutomationGUI(root)
    root.mainloop()
