"""
Comprehensive GKaim Physics Scraper for Class 11 and Class 12.
Scrapes all 28 chapters (over 11,900 MCQs) with complete questions, options (A-D),
correct answers, explanations, and pristine LaTeX math formatting.
Features page-level accumulation, rate-limit tolerance (350ms pacing + backoff),
auto-reauthentication, and smart resume.
"""

import asyncio
import csv
import json
import os
import re
import sys
import time
from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Complete list of chapters with validated URLs
CHAPTERS = [
    # --- Class 11 Physics ---
    {
        "class": "class_11",
        "chap_num": 1,
        "name": "Units and Measurements",
        "folder": "chapter_01_units_and_measurements",
        "expected_mcqs": 394,
        "url": "https://gkaim.com/class-11-physics/units-and-measurements-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 2,
        "name": "Motion in a Straight Line",
        "folder": "chapter_02_motion_in_a_straight_line",
        "expected_mcqs": 400,
        "url": "https://gkaim.com/class-11-physics/motion-in-a-straight-line-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 3,
        "name": "Motion in a Plane",
        "folder": "chapter_03_motion_in_a_plane",
        "expected_mcqs": 443,
        "url": "https://gkaim.com/class-11-physics/motion-in-a-plane-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 4,
        "name": "Laws of Motion",
        "folder": "chapter_04_laws_of_motion",
        "expected_mcqs": 530,
        "url": "https://gkaim.com/class-11-physics/laws-of-motion-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 5,
        "name": "Work, Energy, and Power",
        "folder": "chapter_05_work_energy_and_power",
        "expected_mcqs": 440,
        "url": "https://gkaim.com/class-11-physics/work-energy-and-power-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 6,
        "name": "System of Particles and Rotational Motion",
        "folder": "chapter_06_system_of_particles_and_rotational_motion",
        "expected_mcqs": 480,
        "url": "https://gkaim.com/class-11-physics/system-of-particles-and-rotational-motion-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 7,
        "name": "Gravitation",
        "folder": "chapter_07_gravitation",
        "expected_mcqs": 450,
        "url": "https://gkaim.com/class-11-physics/gravitation-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 8,
        "name": "Mechanical Properties of Solids",
        "folder": "chapter_08_mechanical_properties_of_solids",
        "expected_mcqs": 396,
        "url": "https://gkaim.com/class-11-physics/mechanical-properties-of-solids-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 9,
        "name": "Mechanical Properties of Fluids",
        "folder": "chapter_09_mechanical_properties_of_fluids",
        "expected_mcqs": 439,
        "url": "https://gkaim.com/class-11-physics/mechanical-properties-of-fluids-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 10,
        "name": "Thermal Properties of Matter",
        "folder": "chapter_10_thermal_properties_of_matter",
        "expected_mcqs": 448,
        "url": "https://gkaim.com/class-11-physics/thermal-properties-of-matter-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 11,
        "name": "Thermodynamics",
        "folder": "chapter_11_thermodynamics",
        "expected_mcqs": 500,
        "url": "https://gkaim.com/class-11-physics/thermodynamics-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 12,
        "name": "Kinetic Theory",
        "folder": "chapter_12_kinetic_theory",
        "expected_mcqs": 394,
        "url": "https://gkaim.com/class-11-physics/kinetic-theory-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 13,
        "name": "Oscillations",
        "folder": "chapter_13_oscillations",
        "expected_mcqs": 460,
        "url": "https://gkaim.com/class-11-physics/oscillations-mcqs-part-1/",
    },
    {
        "class": "class_11",
        "chap_num": 14,
        "name": "Waves",
        "folder": "chapter_14_waves",
        "expected_mcqs": 500,
        "url": "https://gkaim.com/class-11-physics/waves-mcqs-part-1/",
    },
    # --- Class 12 Physics ---
    {
        "class": "class_12",
        "chap_num": 1,
        "name": "Electric Charges and Fields",
        "folder": "chapter_01_electric_charges_and_fields",
        "expected_mcqs": 484,
        "url": "https://gkaim.com/class-12-physics/electric-charges-and-fields-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 2,
        "name": "Electrostatic Potential and Capacitance",
        "folder": "chapter_02_electrostatic_potential_and_capacitance",
        "expected_mcqs": 378,
        "url": "https://gkaim.com/class-12-physics/electrostatic-potential-and-capacitance-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 3,
        "name": "Current Electricity",
        "folder": "chapter_03_current_electricity",
        "expected_mcqs": 400,
        "url": "https://gkaim.com/class-12-physics/current-electricity-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 4,
        "name": "Moving Charges and Magnetism",
        "folder": "chapter_04_moving_charges_and_magnetism",
        "expected_mcqs": 360,
        "url": "https://gkaim.com/class-12-physics/moving-charges-and-magnetism-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 5,
        "name": "Magnetism and Matter",
        "folder": "chapter_05_magnetism_and_matter",
        "expected_mcqs": 420,
        "url": "https://gkaim.com/class-12-physics/magnetism-and-matter-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 6,
        "name": "Electromagnetic Induction",
        "folder": "chapter_06_electromagnetic_induction",
        "expected_mcqs": 485,
        "url": "https://gkaim.com/class-12-physics/electromagnetic-induction-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 7,
        "name": "Alternating Current",
        "folder": "chapter_07_alternating_current",
        "expected_mcqs": 400,
        "url": "https://gkaim.com/class-12-physics/alternating-current-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 8,
        "name": "Electromagnetic Waves",
        "folder": "chapter_08_electromagnetic_waves",
        "expected_mcqs": 400,
        "url": "https://gkaim.com/class-12-physics/electromagnetic-waves-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 9,
        "name": "Ray Optics and Optical Instruments",
        "folder": "chapter_09_ray_optics_and_optical_instruments",
        "expected_mcqs": 560,
        "url": "https://gkaim.com/class-12-physics/ray-optics-and-optical-instruments-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 10,
        "name": "Wave Optics",
        "folder": "chapter_10_wave_optics",
        "expected_mcqs": 440,
        "url": "https://gkaim.com/class-12-physics/wave-optics-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 11,
        "name": "Dual Nature of Radiation and Matter",
        "folder": "chapter_11_dual_nature_of_radiation_and_matter",
        "expected_mcqs": 380,
        "url": "https://gkaim.com/class-12-physics/dual-nature-of-radiation-and-matter-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 12,
        "name": "Atoms",
        "folder": "chapter_12_atoms",
        "expected_mcqs": 437,
        "url": "https://gkaim.com/class-12-physics/atoms-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 13,
        "name": "Nuclei",
        "folder": "chapter_13_nuclei",
        "expected_mcqs": 445,
        "url": "https://gkaim.com/class-12-physics/nuclei-mcqs-part-1/",
    },
    {
        "class": "class_12",
        "chap_num": 14,
        "name": "Semiconductor Electronics",
        "folder": "chapter_14_semiconductor_electronics",
        "expected_mcqs": 533,
        "url": "https://gkaim.com/class-12-physics/semiconductor-electronics-materials-devices-and-simple-circuits-mcqs-part-1/",
    },
]

BASE_OUTPUT_DIR = "physics_mcqs"
EMAIL = "hicim68680@juicehour.com"
PASSWORD = "X5BKcgfJyUdHxYE#"


def clean_comment(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<!--.*?-->", "", text).strip()


async def solve_captcha(page) -> int:
    a = int(await page.input_value("input[name='gkaim_sd_captcha_a']"))
    b = int(await page.input_value("input[name='gkaim_sd_captcha_b']"))
    op = await page.input_value("input[name='gkaim_sd_captcha_op']")
    ans = a + b if op == "+" else (a - b if op == "-" else a * b)
    await page.fill("input[name='gkaim_sd_captcha_answer']", str(ans))
    return ans


async def login(page, email, password):
    print(f"[*] Logging in as {email}...")
    await page.goto("https://gkaim.com/student-login/", timeout=60000, wait_until="domcontentloaded")
    await page.wait_for_selector("form:has(input[name='login'])", timeout=30000)
    await page.fill("input[name='login']", email)
    await page.fill("input[name='password']", password)
    await solve_captcha(page)
    await page.click("button.gkaim-sd-btn[type='submit']")
    try:
        await page.wait_for_url("**/student-dashboard/**", timeout=45000)
        print("[+] Login successful! Redirected to Student Dashboard.")
        await page.wait_for_timeout(2000)
    except Exception:
        if "student-dashboard" in page.url or "logged_in" in page.url:
            print(f"[+] Login succeeded (current URL: {page.url})")
            await page.wait_for_timeout(2000)
        else:
            raise RuntimeError(f"Login failed. Current URL: {page.url}")


async def scrape_part_with_resilience(page, part_url, max_retries=3):
    accumulated_mcqs = {}
    expected_total = 100

    for attempt in range(1, max_retries + 1):
        try:
            await page.goto(part_url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector(".gkaim-mcq-root", timeout=30000)
            await page.wait_for_timeout(2000)

            # Get root config
            config = await page.evaluate('''() => {
                const root = document.querySelector(".gkaim-mcq-root");
                const script = document.querySelector(".gkaim-mcq-bootstrap");
                const bootstrap = script ? JSON.parse(script.textContent) : {};
                const total = parseInt(root.getAttribute("data-total") || "100", 10);
                const start = root.getAttribute("data-window-start") || "1";
                const count = root.getAttribute("data-window-total") || "100";
                const perPage = 10;
                const totalPages = Math.ceil(total / perPage);
                return {
                    set: root.getAttribute("data-set"),
                    postId: root.getAttribute("data-post-id"),
                    total, start, count, perPage, totalPages,
                    nonce: bootstrap.nonce,
                    rest: bootstrap.rest
                };
            }''')

            expected_total = config["total"]
            totalPages = config["totalPages"]

            # Determine which pages are still missing
            collected_pages = set()
            for q_num, m in accumulated_mcqs.items():
                if str(q_num).isdigit():
                    q_idx = int(q_num) - int(config["start"])
                    if q_idx >= 0:
                        collected_pages.add((q_idx // 10) + 1)

            missing_pages = [p for p in range(1, totalPages + 1) if p not in collected_pages]
            if not missing_pages and len(accumulated_mcqs) >= expected_total:
                break

            auth_error = False
            for p in missing_pages:
                page_data = await page.evaluate('''async ({ config, p }) => {
                    const u = `${config.rest}?set=${encodeURIComponent(config.set)}&page=${p}&per_page=${config.perPage}&post_id=${config.postId}&start=${config.start}&count=${config.count}`;
                    for (let retry = 0; retry < 4; retry++) {
                        try {
                            const res = await fetch(u, { headers: { 'x-wp-nonce': config.nonce } });
                            if (res.status === 200) {
                                const data = await res.json();
                                if (data.access && data.access.is_logged_in === false) {
                                    return { authError: true, items: [] };
                                }
                                if (data.items) {
                                    return { authError: false, items: data.items };
                                }
                            } else if (res.status === 401 || res.status === 403) {
                                return { authError: true, items: [] };
                            } else {
                                await new Promise(r => setTimeout(r, 2000));
                            }
                        } catch (e) {
                            await new Promise(r => setTimeout(r, 2000));
                        }
                    }
                    return { authError: false, items: [] };
                }''', {"config": config, "p": p})

                if page_data.get("authError"):
                    auth_error = True
                    break

                for item in page_data.get("items", []):
                    q_num = str(item.get("q_no", ""))
                    accumulated_mcqs[q_num] = {
                        "q_no": q_num,
                        "question": clean_comment(item.get("question", "")),
                        "opt_a": clean_comment(item.get("opt_a", "")),
                        "opt_b": clean_comment(item.get("opt_b", "")),
                        "opt_c": clean_comment(item.get("opt_c", "")),
                        "opt_d": clean_comment(item.get("opt_d", "")),
                        "correct": item.get("correct", ""),
                        "explanation": clean_comment(item.get("explanation", "")),
                        "source": "API",
                    }

                await asyncio.sleep(0.35)

            if len(accumulated_mcqs) >= expected_total:
                break
            elif auth_error:
                print(f"        [!] Session auth error on attempt {attempt}, re-authenticating...")
                await login(page, EMAIL, PASSWORD)
                await asyncio.sleep(2)
            else:
                print(f"        [!] Progress ({len(accumulated_mcqs)}/{expected_total}) on attempt {attempt}, pausing 3s before retry...")
                await asyncio.sleep(3)

        except Exception as e:
            print(f"        [!] Exception on attempt {attempt}: {e}")
            await asyncio.sleep(3)

    return list(accumulated_mcqs.values())


def save_chapter_files(chapter_dir, chap_name, mcqs):
    os.makedirs(chapter_dir, exist_ok=True)
    json_path = os.path.join(chapter_dir, f"{chap_name}_all_mcqs.json")
    csv_path = os.path.join(chapter_dir, f"{chap_name}_all_mcqs.csv")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(mcqs, f, indent=2, ensure_ascii=False)

    fieldnames = ["q_no", "question", "opt_a", "opt_b", "opt_c", "opt_d", "correct", "explanation"]
    with open(csv_path, "w", encoding="utf-8", newline="", errors="ignore") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for m in mcqs:
            writer.writerow(m)

    return json_path, csv_path


async def scrape_all():
    summary_report = []

    # Prepare directories
    for c in ["class_11", "class_12"]:
        os.makedirs(os.path.join(BASE_OUTPUT_DIR, c), exist_ok=True)

    # Re-use existing Chapter 1 of Class 11 if available
    chap1_src = os.path.join("chap 1", "chapter_1_all_394_mcqs.json")
    chap1_dest_dir = os.path.join(BASE_OUTPUT_DIR, "class_11", "chapter_01_units_and_measurements")
    if os.path.exists(chap1_src):
        os.makedirs(chap1_dest_dir, exist_ok=True)
        with open(chap1_src, "r", encoding="utf-8") as f:
            c1_mcqs = json.load(f)
        save_chapter_files(chap1_dest_dir, "chapter_01_units_and_measurements", c1_mcqs)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await login(page, EMAIL, PASSWORD)

        total_chapters = len(CHAPTERS)
        for idx, chap in enumerate(CHAPTERS, 1):
            class_name = chap["class"]
            chap_folder = chap["folder"]
            expected = chap["expected_mcqs"]
            target_dir = os.path.join(BASE_OUTPUT_DIR, class_name, chap_folder)
            json_file = os.path.join(target_dir, f"{chap_folder}_all_mcqs.json")

            print(f"\n=======================================================")
            print(f"[{idx}/{total_chapters}] {class_name.upper()} - {chap['name']} (Expected: {expected} MCQs)")
            print(f"=======================================================")

            # Check if already completed and meets expected count
            if os.path.exists(json_file):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    if len(existing) >= expected:
                        print(f"[✓] Already complete: {len(existing)}/{expected} MCQs exist in {json_file}. Skipping.")
                        summary_report.append({
                            "class": class_name,
                            "chapter": chap["name"],
                            "status": "COMPLETED",
                            "count": len(existing),
                            "expected": expected,
                            "file": json_file
                        })
                        continue
                except Exception:
                    pass

            # Step 1: Navigate to Part 1 to discover all part URLs
            target_url = chap["url"]
            if not target_url.endswith("/"):
                target_url += "/"
            print(f"[*] Navigating to Part 1: {target_url}")
            
            nav_ok = False
            for nav_try in range(3):
                try:
                    await page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
                    await page.wait_for_selector(".gkaim-mcq-root", timeout=30000)
                    nav_ok = True
                    break
                except Exception as e:
                    print(f"[!] Error loading Part 1 (attempt {nav_try+1}): {e}")
                    await login(page, EMAIL, PASSWORD)
                    await asyncio.sleep(2)

            if not nav_ok:
                print(f"[X] Failed to load Part 1 for {chap['name']}, skipping chapter...")
                continue

            part_links = await page.evaluate('''() => {
                const links = Array.from(document.querySelectorAll(".button-box a"));
                if (links.length > 0) {
                    return links.map(a => a.href);
                }
                return [window.location.href];
            }''')

            # Filter unique non-empty links preserving order
            unique_parts = []
            for pl in part_links:
                if pl and pl not in unique_parts:
                    unique_parts.append(pl)

            print(f"[+] Found {len(unique_parts)} parts for this chapter")

            chapter_mcqs_dict = {}
            parts_dir = os.path.join(target_dir, "parts")
            os.makedirs(parts_dir, exist_ok=True)

            for p_idx, part_url in enumerate(unique_parts, 1):
                part_mcqs = await scrape_part_with_resilience(page, part_url)
                first_q = part_mcqs[0]["q_no"] if part_mcqs else "?"
                last_q = part_mcqs[-1]["q_no"] if part_mcqs else "?"
                print(f"  --> Part {p_idx}/{len(unique_parts)}: {len(part_mcqs)} MCQs (Q {first_q} to {last_q})")

                # Save individual part JSON
                part_json_path = os.path.join(parts_dir, f"part_{p_idx}.json")
                with open(part_json_path, "w", encoding="utf-8") as f:
                    json.dump(part_mcqs, f, indent=2, ensure_ascii=False)

                for m in part_mcqs:
                    chapter_mcqs_dict[m["q_no"]] = m

                await asyncio.sleep(1.5)

            # Sort and deduplicate
            sorted_mcqs = sorted(
                chapter_mcqs_dict.values(),
                key=lambda x: int(x["q_no"]) if str(x.get("q_no", "")).isdigit() else 999999
            )

            # Save merged chapter files
            final_json, final_csv = save_chapter_files(target_dir, chap_folder, sorted_mcqs)
            print(f"[+] Chapter Finished: {len(sorted_mcqs)}/{expected} MCQs saved to {final_json}")

            summary_report.append({
                "class": class_name,
                "chapter": chap["name"],
                "status": "SUCCESS" if len(sorted_mcqs) >= expected else f"PARTIAL ({len(sorted_mcqs)}/{expected})",
                "count": len(sorted_mcqs),
                "expected": expected,
                "file": final_json
            })

            # Cooldown between chapters
            await asyncio.sleep(2.5)

        await browser.close()

    # Save summary report
    summary_file = os.path.join(BASE_OUTPUT_DIR, "scraping_summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary_report, f, indent=2)

    print("\n" + "="*60)
    print("ALL CHAPTERS SCRAPING PROCESS COMPLETED!")
    print(f"Summary written to: {summary_file}")
    print("="*60)


if __name__ == "__main__":
    start_time = time.time()
    asyncio.run(scrape_all())
    elapsed = time.time() - start_time
    print(f"Elapsed Time: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
