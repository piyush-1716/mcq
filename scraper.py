"""
GKaim MCQ Scraper using Python Playwright
Scrapes multiple choice questions, options, correct answers, and explanations.
Handles login authentication, math security captcha, and paginated dynamic content.
"""

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Ensure standard output doesn't crash on Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class GKaimScraper:
    def __init__(self, email: str, password: str, headless: bool = True):
        self.email = email
        self.password = password
        self.headless = headless
        self.mcqs = {}  # keyed by question number (int or str)

    async def solve_captcha(self, page) -> int:
        """Solves the arithmetic security check on the login form."""
        a = int(await page.input_value("input[name='gkaim_sd_captcha_a']"))
        b = int(await page.input_value("input[name='gkaim_sd_captcha_b']"))
        op = await page.input_value("input[name='gkaim_sd_captcha_op']")

        if op == "+":
            ans = a + b
        elif op == "-":
            ans = a - b
        elif op == "*":
            ans = a * b
        else:
            ans = a + b

        print(f"[*] Solving login captcha: {a} {op} {b} = {ans}")
        await page.fill("input[name='gkaim_sd_captcha_answer']", str(ans))
        return ans

    async def login(self, page):
        """Logs into GKaim student portal."""
        print(f"[*] Navigating to login page: https://gkaim.com/student-login/ ...")
        await page.goto("https://gkaim.com/student-login/", timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_selector("form:has(input[name='login'])", timeout=30000)

        print(f"[*] Entering credentials for {self.email}...")
        await page.fill("input[name='login']", self.email)
        await page.fill("input[name='password']", self.password)

        await self.solve_captcha(page)

        print("[*] Submitting login form...")
        await page.click("button.gkaim-sd-btn[type='submit']")

        try:
            await page.wait_for_url("**/student-dashboard/**", timeout=45000)
            print("[+] Login successful! Redirected to Student Dashboard.")
        except Exception:
            # Check if still on login or redirected elsewhere
            if "student-dashboard" in page.url or "logged_in" in page.url:
                print(f"[+] Login succeeded (current URL: {page.url})")
            else:
                alert = await page.query_selector(".gkaim-sd-alert, .gkaim-sd-error")
                if alert:
                    msg = await alert.inner_text()
                    raise RuntimeError(f"Login failed: {msg}")
                raise RuntimeError(f"Login timeout. Current URL: {page.url}")

    def parse_dom_question(self, container_html: str) -> dict:
        """Parses a pre-rendered question container from the DOM."""
        soup = BeautifulSoup(container_html, "html.parser")

        # Replace MathJax elements with readable text from assistive MathML
        for mjx in soup.find_all("mjx-container"):
            mml = mjx.find("mjx-assistive-mml")
            if mml:
                math_txt = mml.get_text(separator=" ", strip=True)
                mjx.replace_with(f" {math_txt} ")
            else:
                mjx.replace_with(f" {mjx.get_text(strip=True)} ")

        q_el = soup.find(class_="question")
        q_no = None
        q_text = ""
        if q_el:
            raw_q = q_el.get_text(separator=" ", strip=True)
            m = re.match(r"^(\d+)\.\s*(.*)", raw_q)
            if m:
                q_no = m.group(1)
                q_text = m.group(2)
            else:
                q_text = raw_q

        # Extract options (a, b, c, d)
        options = {}
        correct_letter = None
        opt_els = soup.find_all(class_="option")
        for i, opt in enumerate(opt_els):
            letter = chr(ord("A") + i)
            if opt.get("data-answer") == "true":
                correct_letter = letter

            t_el = opt.find(class_="option-text") or opt
            t = t_el.get_text(separator=" ", strip=True)
            t = re.sub(r"^[ⓐⓑⓒⓓⓔa-eA-E][\.\)\s]*", "", t).strip()
            options[f"opt_{letter.lower()}"] = t

        # Extract explanation
        exp_el = soup.find(class_="explanation")
        exp_text = ""
        if exp_el:
            raw_exp = exp_el.get_text(separator=" ", strip=True)
            if "Explanation:" in raw_exp:
                exp_text = raw_exp.split("Explanation:", 1)[1].strip()
            else:
                exp_text = raw_exp

        return {
            "q_no": str(q_no) if q_no else "",
            "question": re.sub(r"\s+", " ", q_text).strip(),
            "opt_a": re.sub(r"\s+", " ", options.get("opt_a", "")).strip(),
            "opt_b": re.sub(r"\s+", " ", options.get("opt_b", "")).strip(),
            "opt_c": re.sub(r"\s+", " ", options.get("opt_c", "")).strip(),
            "opt_d": re.sub(r"\s+", " ", options.get("opt_d", "")).strip(),
            "correct": correct_letter or "",
            "explanation": re.sub(r"\s+", " ", exp_text).strip(),
            "source": "DOM",
        }

    async def scrape(self, target_url: str) -> list:
        """Main scraping workflow: logs in and navigates through all MCQ pages."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            page = await context.new_page()

            # Set up API response interceptor
            async def on_response(response):
                if "gkaim/v1/mcqs" in response.url and response.status == 200:
                    try:
                        data = await response.json()
                        items = data.get("items", [])
                        if items:
                            page_num = data.get("page", "?")
                            print(f"[+] Intercepted API response for page {page_num}: {len(items)} MCQs")
                            for item in items:
                                q_num = str(item.get("q_no", ""))
                                item_clean = {
                                    "q_no": q_num,
                                    "question": clean_comment(item.get("question", "")),
                                    "opt_a": item.get("opt_a", ""),
                                    "opt_b": item.get("opt_b", ""),
                                    "opt_c": item.get("opt_c", ""),
                                    "opt_d": item.get("opt_d", ""),
                                    "correct": item.get("correct", ""),
                                    "explanation": item.get("explanation", ""),
                                    "source": "API",
                                }
                                # API data has pristine LaTeX formatting, save or update
                                self.mcqs[q_num] = item_clean
                    except Exception:
                        pass

            page.on("response", on_response)

            # 1. Login
            await self.login(page)

            # 2. Open Target URL
            print(f"[*] Navigating to MCQ page: {target_url}...")
            await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector(".gkaim-mcq-root", timeout=30000)
            await page.wait_for_timeout(2000)

            # Read root config attributes
            root = await page.query_selector(".gkaim-mcq-root")
            total_count = int(await root.get_attribute("data-total") or 100)
            per_page = int(await root.get_attribute("data-per-page") or 10)
            total_pages = (total_count + per_page - 1) // per_page
            print(f"[+] Total questions in this set: {total_count} ({total_pages} pages)")

            # 3. Harvest pre-rendered questions from DOM (typically pages 1 & 2)
            pre_rendered = await page.query_selector_all(".quiz-page .question-container")
            print(f"[*] Processing {len(pre_rendered)} pre-rendered question containers from DOM...")
            for qc in pre_rendered:
                html = await qc.inner_html()
                parsed = self.parse_dom_question(html)
                if parsed.get("q_no") and parsed["q_no"] not in self.mcqs:
                    self.mcqs[parsed["q_no"]] = parsed

            print(f"[+] Total MCQs initially collected: {len(self.mcqs)}")

            # 4. Navigate through all remaining pagination pages
            for target_page in range(3, total_pages + 1):
                print(f"[*] Navigating to page {target_page}/{total_pages}...")

                # Click page number or 'Next'
                btn = await page.query_selector(f"nav.pagination button:has-text('{target_page}')")
                if not btn:
                    btn = await page.query_selector("nav.pagination button:has-text('Next')")

                if btn:
                    await btn.click()
                    # Wait for API fetch and DOM update
                    await page.wait_for_timeout(2500)
                else:
                    print(f"[-] Could not find button for page {target_page}")

            await browser.close()

        # Sort all MCQs by numerical question number
        sorted_mcqs = sorted(
            self.mcqs.values(),
            key=lambda x: int(x["q_no"]) if str(x.get("q_no", "")).isdigit() else 999999,
        )
        print(f"\n[+] Scraping complete! Successfully scraped {len(sorted_mcqs)} MCQs.")
        return sorted_mcqs


def clean_comment(text: str) -> str:
    """Removes HTML comments like <!--gkaim:...--> from text."""
    if not text:
        return ""
    return re.sub(r"<!--.*?-->", "", text).strip()


def save_to_json(mcqs: list, filename: str):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(mcqs, f, indent=2, ensure_ascii=False)
    print(f"[+] JSON output saved to: {os.path.abspath(filename)}")


def save_to_csv(mcqs: list, filename: str):
    fieldnames = ["q_no", "question", "opt_a", "opt_b", "opt_c", "opt_d", "correct", "explanation"]
    with open(filename, "w", encoding="utf-8", newline="", errors="ignore") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for m in mcqs:
            writer.writerow(m)
    print(f"[+] CSV output saved to: {os.path.abspath(filename)}")


def main():
    parser = argparse.ArgumentParser(description="Scrape MCQs from GKaim.com using Playwright.")
    parser.add_argument(
        "--url",
        default="https://gkaim.com/class-11-physics/units-and-measurements-mcqs-part-1/",
        help="GKaim MCQ page URL to scrape.",
    )
    parser.add_argument("--email", default="hicim68680@juicehour.com", help="GKaim login email/username.")
    parser.add_argument("--password", default="X5BKcgfJyUdHxYE#", help="GKaim login password.")
    parser.add_argument(
        "--output",
        default="units_and_measurements_mcqs_part_1",
        help="Base name for output files (will generate .json and .csv).",
    )
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode (visible window).")

    args = parser.parse_args()

    scraper = GKaimScraper(
        email=args.email,
        password=args.password,
        headless=not args.headed,
    )

    mcqs = asyncio.run(scraper.scrape(args.url))

    if mcqs:
        json_file = f"{args.output}.json"
        csv_file = f"{args.output}.csv"
        save_to_json(mcqs, json_file)
        save_to_csv(mcqs, csv_file)


if __name__ == "__main__":
    main()
