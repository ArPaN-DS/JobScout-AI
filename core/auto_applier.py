import asyncio
import os
import json
import random
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from playwright.async_api import async_playwright, Page, BrowserContext, Browser, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

from django.conf import settings
from .llm import LLMRouter, LLMRequest, LLMTask
from .resilience import classify_error, ErrorType, screenshot_on_failure

# 
# VIEWPORTS & USER AGENTS FOR AUTHENTICITY
# 

VIEWPORTS = [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1920, "height": 1080},
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

# 
# STEALTH BROWSER FACTORY
# 

async def create_stealth_browser(
    playwright_instance,
    headless: bool = True,
    profile_name: str = "default"
) -> Tuple[BrowserContext, Page]:
    """Launches a chromium instance under playwright with heavy anti-detection patches."""
    viewport = random.choice(VIEWPORTS)
    user_agent = random.choice(USER_AGENTS)

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--no-first-run",
        "--no-default-browser-check",
        f"--window-size={viewport['width']},{viewport['height']}",
    ]

    context_options = {
        "user_agent": user_agent,
        "viewport": viewport,
        "timezone_id": "Asia/Kolkata",
        "locale": "en-IN",
        "color_scheme": "light",
        "accept_downloads": True,
        "java_script_enabled": True,
    }

    # Use persistent contexts to retain login states and session cookies
    sessions_dir = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media")) / "browser_sessions" / profile_name
    sessions_dir.mkdir(parents=True, exist_ok=True)

    context = await playwright_instance.chromium.launch_persistent_context(
        str(sessions_dir),
        headless=headless,
        args=launch_args,
        **context_options
    )

    page = context.pages[0] if context.pages else await context.new_page()
    
    # Apply stealth scripts
    stealth = Stealth()
    await stealth.apply_stealth_async(page)
    
    return context, page


# 
# HUMAN BEHAVIOR SIMULATIONS
# 

async def human_move_to(page: Page, x: float, y: float):
    """Moves cursor to (x, y) direct but with slight natural delay."""
    await page.mouse.move(x, y)
    await asyncio.sleep(random.uniform(0.05, 0.15))


async def human_click(page: Page, selector: str, timeout: int = 5000):
    """Clicks an element naturally after acquiring its bounding box."""
    try:
        locator = page.locator(selector).first
        await locator.wait_for(state="visible", timeout=timeout)
        box = await locator.bounding_box()

        if not box:
            await locator.click(timeout=timeout)
            return

        # Click slightly off-center for human authenticity
        click_x = box["x"] + random.uniform(0.2, 0.8) * box["width"]
        click_y = box["y"] + random.uniform(0.2, 0.8) * box["height"]

        await human_move_to(page, click_x, click_y)
        await asyncio.sleep(random.uniform(0.05, 0.15))
        await page.mouse.click(click_x, click_y)
        await asyncio.sleep(random.uniform(0.1, 0.3))
    except Exception:
        # Direct click fallback
        await page.locator(selector).first.click(timeout=timeout)


async def human_type(page: Page, selector: str, text: str, clear_first: bool = True):
    """Types text character-by-character with natural reaction pauses and minor typos."""
    try:
        locator = page.locator(selector).first
        await locator.wait_for(state="visible", timeout=5000)
        await human_click(page, selector)
        await asyncio.sleep(random.uniform(0.1, 0.2))

        if clear_first:
            await page.keyboard.press("Control+a")
            await asyncio.sleep(random.uniform(0.05, 0.1))
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.1, 0.2))

        for char in text:
            # 3% chance of typo
            if random.random() < 0.03 and len(text) > 4 and char.isalpha():
                wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                await page.keyboard.type(wrong_char, delay=random.randint(60, 150))
                await asyncio.sleep(random.uniform(0.1, 0.2))
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.08, 0.15))

            delay = max(30, int(random.gauss(100, 30)))
            await page.keyboard.type(char, delay=delay)
            
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.2, 0.6))  # thinking pause
    except Exception:
        await page.locator(selector).first.fill(text)


async def human_scroll(page: Page, direction: str = "down", distance: int = None):
    """Gradually scrolls page in chunks to simulate reading."""
    if distance is None:
        distance = random.randint(200, 500)
    multiplier = 1 if direction == "down" else -1
    
    segments = random.randint(3, 5)
    for i in range(segments):
        seg_dist = (distance // segments + random.randint(-15, 15)) * multiplier
        await page.mouse.wheel(0, seg_dist)
        await asyncio.sleep(random.uniform(0.05, 0.15))


async def simulate_reading(page: Page, duration_range: Tuple[int, int] = (2, 4)):
    """Simulates natural reader interactions."""
    read_time = random.uniform(*duration_range)
    elapsed = 0.0
    while elapsed < read_time:
        action = random.choice(["scroll_down", "pause", "mouse_idle"])
        if action == "scroll_down":
            await human_scroll(page, "down")
            elapsed += 0.5
        elif action == "pause":
            pause_time = random.uniform(0.5, 1.5)
            await asyncio.sleep(pause_time)
            elapsed += pause_time
        elif action == "mouse_idle":
            await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
            elapsed += 0.4


async def page_load_settle(page: Page):
    """Wait for DOM to load and let the browser settle naturally."""
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
    await asyncio.sleep(random.uniform(1.0, 2.5))


# 
# ADAPTIVE SELF-HEALING SELECTORS
# 

async def find_element_fuzzy(page: Page, selectors: List[str], keywords: List[str]) -> Optional[str]:
    """
    Self-healing selector system:
    1. Tries exact CSS selectors.
    2. Tries fuzzy matching using text-similarity (searching for keywords in page anchors/buttons).
    """
    # 1. Try exact CSS selectors
    for selector in selectors:
        try:
            el = page.locator(selector).first
            if await el.count() > 0 and await el.is_visible():
                return selector
        except Exception:
            continue

    # 2. Try Scrapling/Fuzzy text-similarity matches on interactive elements
    for kw in keywords:
        try:
            # Match buttons/links containing target text
            xpath_selectors = [
                f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw}')]",
                f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw}')]",
                f"//input[@type='submit' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw}')]",
                f"//*[@role='button' and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw}')]"
            ]
            for xpath in xpath_selectors:
                el = page.locator(xpath).first
                if await el.count() > 0 and await el.is_visible():
                    print(f"   Self-healing selector matched element via XPath: {xpath}")
                    return xpath
        except Exception:
            continue

    return None


# 
# FORM FIELD EXTRACTION & LLM SMART FILL
# 

async def extract_form_fields(page: Page) -> List[Dict[str, Any]]:
    """Extracts descriptive metadata of all visible form inputs on the current page."""
    try:
        fields = await page.evaluate("""
            () => {
                const fields = [];
                const inputs = document.querySelectorAll('input, select, textarea');
                for (const el of inputs) {
                    if (el.offsetParent === null) continue; // skip hidden
                    
                    let label = '';
                    if (el.labels && el.labels.length > 0) {
                        label = el.labels[0].textContent.trim();
                    }
                    if (!label) {
                        label = el.getAttribute('aria-label') || 
                                el.getAttribute('placeholder') || 
                                el.getAttribute('name') || 
                                el.id || '';
                    }
                    
                    const field = {
                        tag: el.tagName.toLowerCase(),
                        type: el.type || 'text',
                        name: el.name || el.id || '',
                        id: el.id || '',
                        label: label.trim(),
                        placeholder: el.placeholder || '',
                        required: el.required || false,
                        value: el.value || '',
                        options: []
                    };
                    
                    if (el.tagName === 'SELECT') {
                        field.options = Array.from(el.options).map(o => ({
                            value: o.value, text: o.textContent.trim()
                        }));
                    }
                    fields.push(field);
                }
                return fields;
            }
        """)
        return fields
    except Exception as e:
        print(f"  Form field extraction failed: {e}")
        return []


async def smart_fill_form(fields: List[Dict[str, Any]], profile: Dict[str, Any]) -> Dict[str, Any]:
    """Uses LLMRouter to map profile claims and form inputs intelligently with zero-prompt fallback."""
    if not fields:
        return {}

    field_descriptions = []
    for f in fields:
        desc = f"- Field: name='{f['name']}', label='{f['label']}', type='{f['type']}'"
        if f.get("options"):
            opts = [o["text"] for o in f["options"][:6]]
            desc += f", options={opts}"
        if f.get("placeholder"):
            desc += f", placeholder='{f['placeholder']}'"
        if f.get("required"):
            desc += " (REQUIRED)"
        field_descriptions.append(desc)

    prompt = f"""You are filling out a job application form. Map the candidate's profile data to the form fields.

CANDIDATE PROFILE:
- Full Name: {profile.get('name', 'Candidate Name')}
- Email: {profile.get('email', '')}
- Phone: {profile.get('phone', '')}
- Location: {profile.get('location', '')}
- Target Roles: {profile.get('target_roles', [])}
- Skills: {profile.get('skills', [])}
- Experience: {profile.get('experience', [])}
- LinkedIn: {profile.get('linkedin_url', '')}
- GitHub: {profile.get('github_url', '')}
- Work Authorization: {profile.get('visa_status', '')}

FORM FIELDS:
{chr(10).join(field_descriptions)}

Return ONLY a valid JSON object mapping the field 'name' (or 'id' if name is empty) to the value to fill.
For select/dropdown fields, return the exact option value or option text matching the candidate profile.
For checkbox/radio buttons, return a boolean (true/false) or the option string.
IMPORTANT: Return ONLY the JSON, no markdown, no explanation."""

    try:
        router = LLMRouter()
        result = router.generate(
            LLMRequest(
                task=LLMTask.CRITIC_VALIDATE,
                prompt=prompt,
                temperature=0.1,
                response_mime_type="application/json"
            )
        )
        text = result.text.strip()
        
        # Clean JSON markdown if any
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        mapping = json.loads(text)
        print(f"  LLM mapped {len(mapping)} fields dynamically.")
        return mapping
    except Exception as e:
        print(f"  LLM smart fill failed: {e}. Falling back to basic heuristics.")
        
        # Fallback basic heuristics
        mapping = {}
        for f in fields:
            label = (f["name"] + f["label"] + f["placeholder"]).lower()
            key = f["name"] or f["id"]
            if not key:
                continue
            if "first" in label or "fname" in label:
                mapping[key] = profile.get("name", "").split()[0] if profile.get("name") else ""
            elif "last" in label or "lname" in label:
                parts = profile.get("name", "").split()
                mapping[key] = parts[-1] if len(parts) > 1 else ""
            elif "name" in label:
                mapping[key] = profile.get("name", "")
            elif "email" in label:
                mapping[key] = profile.get("email", "")
            elif "phone" in label or "mobile" in label or "tel" in label:
                mapping[key] = profile.get("phone", "")
            elif "linkedin" in label:
                mapping[key] = profile.get("linkedin_url", "")
            elif "github" in label:
                mapping[key] = profile.get("github_url", "")
        return mapping


async def fill_field(page: Page, field: Dict[str, Any], value: str):
    """Enters value into a single form input using human-like keyboard delays."""
    selector = f"#{field['id']}" if field.get("id") else f"[name='{field['name']}']" if field.get("name") else ""
    if not selector:
        return

    try:
        el = page.locator(selector).first
        if await el.count() == 0 or not await el.is_visible():
            return

        tag = field.get("tag", "input")
        ftype = field.get("type", "text")

        if tag == "select":
            await el.select_option(value=value)
            await asyncio.sleep(random.uniform(0.3, 0.6))
        elif ftype in ("checkbox", "radio"):
            if str(value).lower() in ("true", "yes", "1", "on"):
                await human_click(page, selector)
        elif tag == "textarea":
            await human_type(page, selector, value)
        else:
            await human_type(page, selector, value)
    except Exception as e:
        print(f"     Failed to fill field {selector}: {e}")


# 
# MAIN AUTO APPLY PIPELINE
# 

async def try_auto_apply(
    apply_url: str,
    pdf_path: str,
    profile_data: dict,
    auto_submit: bool = False
) -> Tuple[bool, str, str, str]:
    """
    Core Playwright Stealth Auto-Apply pipeline.
    
    Returns: (success: bool, status_message: str, relative_screenshot_path: str, error_message: str)
    """
    print(f"  [AutoApply] Starting apply for: {apply_url[:60]}...")
    
    # Check if URL is blank
    if not apply_url:
        return False, "failed", "", "Blank URL provided."

    portal_name = "generic"
    if "linkedin" in apply_url.lower():
        portal_name = "linkedin"
    elif "internshala" in apply_url.lower():
        portal_name = "internshala"
    elif "greenhouse" in apply_url.lower():
        portal_name = "greenhouse"
    elif "lever" in apply_url.lower():
        portal_name = "lever"

    screenshot_rel = ""
    error_msg = ""

    async with async_playwright() as p:
        try:
            # 1. Create stealth browser context
            context, page = await create_stealth_browser(p, headless=True, profile_name=portal_name)

            # 2. Navigate to page
            await page.goto(apply_url, timeout=30000, wait_until="domcontentloaded")
            await page_load_settle(page)

            # 3. Simulate human reading the listing
            await simulate_reading(page, (2, 3))

            # 4. Handle CAPTCHA blocks
            content = await page.content()
            if classify_error(page_content=content) == ErrorType.BOT_BLOCKED:
                screenshot_rel = await screenshot_on_failure(page, portal_name, "bot_blocked")
                return False, "failed", screenshot_rel or "", "CAPTCHA or Cloudflare bot block detected."

            # 5. Look for Apply Button
            apply_selectors = [
                "button:has-text('Apply')", "a:has-text('Apply')",
                "button:has-text('Easy Apply')", "button:has-text('Quick Apply')",
                "button:has-text('Apply Now')", "a:has-text('Apply Now')"
            ]
            apply_keywords = ["apply", "easy apply", "quick apply", "apply now", "submit application"]
            
            apply_xpath = await find_element_fuzzy(page, apply_selectors, apply_keywords)
            if apply_xpath:
                await human_click(page, apply_xpath)
                await page_load_settle(page)

            # 6. Check for Resume Upload Inputs
            file_inputs = page.locator("input[type='file']")
            if await file_inputs.count() > 0:
                try:
                    # Resolve absolute path to PDF
                    absolute_pdf_path = os.path.join(settings.MEDIA_ROOT, pdf_path)
                    if os.path.exists(absolute_pdf_path):
                        await file_inputs.first.set_input_files(absolute_pdf_path)
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        print("  [AutoApply]  Tailored resume PDF uploaded successfully.")
                except Exception as ex:
                    print(f"   Resume upload failed: {ex}")

            # 7. Form Field Extraction & Smart Fill
            fields = await extract_form_fields(page)
            if fields:
                print(f"  [AutoApply] Found {len(fields)} fields. Performing smart fill...")
                mapping = await smart_fill_form(fields, profile_data)
                
                for field in fields:
                    key = field["name"] or field["id"]
                    if key in mapping and mapping[key] is not None:
                        await fill_field(page, field, str(mapping[key]))
                
                await asyncio.sleep(random.uniform(1.0, 2.0))

            # 8. Save Form-Filled Screenshot
            screenshot_rel = await screenshot_on_failure(page, portal_name, "form_filled")

            # 9. Form Submission or Safety Fallback
            if auto_submit:
                submit_selectors = ["button[type='submit']", "input[type='submit']", "button:has-text('Submit')", "button:has-text('Send')"]
                submit_keywords = ["submit", "send application", "submit application"]
                
                submit_xpath = await find_element_fuzzy(page, submit_selectors, submit_keywords)
                if submit_xpath:
                    await human_click(page, submit_xpath)
                    await page_load_settle(page)
                    
                    # Capture final successful state
                    screenshot_rel = await screenshot_on_failure(page, portal_name, "submitted")
                    await context.close()
                    return True, "auto_applied", screenshot_rel or "", ""
                else:
                    await context.close()
                    return False, "manual_required", screenshot_rel or "", "Form filled, but submit button could not be located."
            else:
                await context.close()
                return False, "manual_required", screenshot_rel or "", "Form filled successfully (safety mode: manual submit required)."

        except PlaywrightTimeoutError:
            error_msg = "Page load timeout (PlaywrightTimeoutError)."
            print(f"   [AutoApply] Timeout: {error_msg}")
            return False, "failed", "", error_msg
        except Exception as e:
            error_type = classify_error(error=e)
            error_msg = f"{error_type.value}: {str(e)[:150]}"
            print(f"   [AutoApply] Critical error during apply: {error_msg}")
            return False, "failed", "", error_msg
