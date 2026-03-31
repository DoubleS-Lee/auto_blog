"""
네이버 로그인 쿠키 저장 스크립트 (최초 1회 실행)

브라우저가 열리면 네이버에 직접 로그인 후 Enter를 누르면
session/naver_cookies.json에 쿠키가 저장됩니다.
이후 main.py 실행 시 자동 로그인됩니다.
"""
import json
import os
from playwright.sync_api import sync_playwright

COOKIE_PATH = "session/naver_cookies.json"


def save_login():
    if os.path.exists(COOKIE_PATH):
        print(f"[!] 이미 쿠키 파일이 있습니다: {COOKIE_PATH}")
        answer = input("다시 로그인하여 갱신하시겠습니까? (y/n): ").strip().lower()
        if answer != "y":
            print("취소되었습니다.")
            return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://nid.naver.com/nidlogin.login")
        print("\n[→] 브라우저에서 네이버 로그인을 완료하세요.")
        print("[→] 로그인 완료 후 여기서 Enter를 누르세요...")
        input()

        cookies = context.cookies()
        os.makedirs("session", exist_ok=True)
        with open(COOKIE_PATH, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        browser.close()

    print(f"[✓] 쿠키 저장 완료: {COOKIE_PATH}")
    print("[✓] 이제 main.py를 실행하면 자동 로그인됩니다.")


if __name__ == "__main__":
    save_login()
