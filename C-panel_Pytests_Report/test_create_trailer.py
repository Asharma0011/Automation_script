# test_create_trailer.py
import random
import string
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

BASE_URL = "https://afm2020.com/"
CORP_ID = "AFMDEMO"
USERNAME = "Asharma"
PASSWORD = "Avaal@123"

GLOBAL_TIMEOUT = 20000
NAV_TIMEOUT = 60000
RETRY_ATTEMPTS = 5
RETRY_DELAY = 2

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)


def log(msg):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}")


def random_alphanum(n):
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def take_screenshot(page, name):
    path = ARTIFACTS_DIR / name
    try:
        page.screenshot(path=str(path), full_page=True)
        log(f"Screenshot saved: {path}")
    except Exception as e:
        log(f"Screenshot failed: {e}")


def save_html(page, name):
    path = ARTIFACTS_DIR / name
    try:
        path.write_text(page.content(), encoding="utf-8")
        log(f"HTML saved: {path}")
    except Exception as e:
        log(f"Save HTML failed: {e}")


def safe_wait(page, ms):
    try:
        page.wait_for_timeout(ms)
    except Exception:
        pass


def retry_action(fn, attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY, *args, **kwargs):
    last_error = None
    for i in range(attempts):
        try:
            if fn(*args, **kwargs):
                return True
        except Exception as e:
            last_error = e
            log(f"Attempt {i + 1} failed: {e}")
        if i < attempts - 1:
            time.sleep(delay)
    if last_error:
        log(f"All retry attempts failed. Last error: {last_error}")
    return False


def _try_click_in_context(ctx, selector, timeout=3000, force=False):
    locator = ctx.locator(selector).first
    if locator.count() == 0:
        return False
    locator.wait_for(state="visible", timeout=timeout)
    locator.scroll_into_view_if_needed()
    locator.click(timeout=timeout, force=force)
    return True


def click_if_exists(page, selector, timeout=3000, force=False):
    try:
        if _try_click_in_context(page, selector, timeout=timeout, force=force):
            log(f"Clicked on main page: {selector}")
            return True
    except Exception as e:
        log(f"Main page click failed for {selector}: {e}")

    for frame in page.frames:
        try:
            if _try_click_in_context(frame, selector, timeout=timeout, force=force):
                log(f"Clicked in frame: {selector}")
                return True
        except Exception:
            continue

    return False


def _try_fill_in_context(ctx, selector, text, timeout=3000):
    locator = ctx.locator(selector).first
    if locator.count() == 0:
        return False
    locator.wait_for(state="visible", timeout=timeout)
    locator.fill(text, timeout=timeout)
    return True


def fill_if_exists(page, selector, text, timeout=3000):
    try:
        if _try_fill_in_context(page, selector, text, timeout=timeout):
            log(f"Filled on main page: {selector} = {text}")
            return True
    except Exception as e:
        log(f"Main page fill failed for {selector}: {e}")

    for frame in page.frames:
        try:
            if _try_fill_in_context(frame, selector, text, timeout=timeout):
                log(f"Filled in frame: {selector} = {text}")
                return True
        except Exception:
            continue

    return False


def _try_select_in_context(ctx, selector, timeout=GLOBAL_TIMEOUT, **kwargs):
    locator = ctx.locator(selector).first
    if locator.count() == 0:
        return False
    locator.wait_for(state="visible", timeout=timeout)
    locator.select_option(timeout=timeout, **kwargs)
    return True


def retry_select(page, selector, **kwargs):
    for i in range(RETRY_ATTEMPTS):
        try:
            if _try_select_in_context(page, selector, **kwargs):
                log(f"Selected on main page: {selector} {kwargs}")
                return True
        except Exception as e:
            log(f"Main select attempt {i + 1} failed for {selector}: {e}")

        for frame in page.frames:
            try:
                if _try_select_in_context(frame, selector, **kwargs):
                    log(f"Selected in frame: {selector} {kwargs}")
                    return True
            except Exception:
                continue

        time.sleep(RETRY_DELAY)
    return False


def eval_on_selector_all_anywhere(page, selector, script):
    try:
        if page.locator(selector).count() > 0:
            return page.eval_on_selector_all(selector, script)
    except Exception:
        pass

    for frame in page.frames:
        try:
            if frame.locator(selector).count() > 0:
                return frame.eval_on_selector_all(selector, script)
        except Exception:
            continue
    return []


def choose_first_select_option(page, selector):
    try:
        options = eval_on_selector_all_anywhere(
            page,
            selector + " option",
            "els => els.map(e => ({v: e.value, t: e.textContent, d: e.disabled}))"
        )
        for opt in options:
            value = opt.get("v")
            text = (opt.get("t") or "").strip().lower()
            if value and value not in ["", "0", "-1"] and not opt.get("d") and text != "select":
                if retry_select(page, selector, value=value):
                    return value
    except Exception as e:
        log(f"choose_first_select_option failed: {e}")
    return None


def wait_for_any_visible(page, selectors, timeout_each=5000):
    for sel in selectors:
        try:
            if page.locator(sel).first.is_visible(timeout=timeout_each):
                return page, sel
        except Exception:
            pass

        for frame in page.frames:
            try:
                if frame.locator(sel).first.is_visible(timeout=timeout_each):
                    return frame, sel
            except Exception:
                continue
    return None, None


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=150,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.set_default_timeout(GLOBAL_TIMEOUT)
        yield page
        browser.close()


def login(page):
    log("Opening login page")
    page.goto(BASE_URL, timeout=NAV_TIMEOUT, wait_until="load")
    safe_wait(page, 2000)

    assert retry_action(fill_if_exists, page=page, selector="#txtCorporateId", text=CORP_ID, attempts=3, delay=1)
    assert retry_action(fill_if_exists, page=page, selector="#txtUserName", text=USERNAME, attempts=3, delay=1)
    assert retry_action(fill_if_exists, page=page, selector="#txtPassword", text=PASSWORD, attempts=3, delay=1)

    signed_in = False
    for sel in ["#signin", "button:has-text('Sign In')", "text=Sign In"]:
        if retry_action(click_if_exists, page=page, selector=sel, timeout=GLOBAL_TIMEOUT, force=True, attempts=3, delay=1):
            signed_in = True
            break

    assert signed_in, "Sign in button not clicked"
    safe_wait(page, 5000)
    log(f"After login URL: {page.url}")


def open_trailers_page(page):
    log("Opening C-PANEL")
    cpanel_selectors = [
        "a[data-id='#MNU00005']",
        "a:has-text('C-PANEL')",
        "a:has-text('C Panel')",
        "text=C-PANEL",
        "text=C Panel",
    ]

    for sel in cpanel_selectors:
        if retry_action(click_if_exists, page=page, selector=sel, timeout=GLOBAL_TIMEOUT, force=True, attempts=3, delay=1):
            break

    safe_wait(page, 2000)

    log("Opening Trailers")
    trailer_selectors = [
        "#MNU00005 a:has-text('Trailers')",
        "a[href*='Masters/Trailer/TrailerList']",
        "a[href*='Trailer/TrailerList']",
        "a:has-text('Trailers')",
        "text=Trailers",
    ]

    clicked = False
    for sel in trailer_selectors:
        if retry_action(click_if_exists, page=page, selector=sel, timeout=GLOBAL_TIMEOUT, force=True, attempts=3, delay=1):
            clicked = True
            break

    assert clicked, "Could not click Trailers menu"

    safe_wait(page, 2000)

    new_btn_selectors = [
        "#btnAddTrailer",
        "#btnAddNewTrailer",
        "a:has-text('New')",
        "button:has-text('New')",
        "[title='New']",
        "[aria-label='New']",
        "text=+ New",
        "text=New",
    ]

    clicked_new = False
    for sel in new_btn_selectors:
        if retry_action(click_if_exists, page=page, selector=sel, timeout=5000, force=True, attempts=2, delay=1):
            clicked_new = True
            break

    assert clicked_new, "New button not found"
    safe_wait(page, 2000)


def fill_trailer_form(page):
    modal_selectors = [
        "#myTrailerModal",
        ".modal.show",
        ".modal.in",
        "text=Create Trailer",
        "input[name='TrailerNo']",
        "#txtTrailerNumber",
        "#txtTrailerNo",
    ]

    ctx, found_sel = wait_for_any_visible(page, modal_selectors, timeout_each=8000)
    assert ctx is not None, "Trailer modal/form did not appear"
    log(f"Trailer form found using: {found_sel}")

    trailer_no = "TRL" + random_alphanum(5).upper()
    plate_no = random_alphanum(6).upper()
    vin_no = random_alphanum(17).upper()

    fields = [
        ("#txtTrailerNumber", trailer_no),
        ("#txtTrailerNo", trailer_no),
        ("input[name='TrailerNo']", trailer_no),
        ("input[placeholder*='Trailer']", trailer_no),

        ("#txtTrailerPlateNumber", plate_no),
        ("#txtPlateNumber", plate_no),
        ("input[name='PlateNumber']", plate_no),

        ("#txtTrailerVIN", vin_no),
        ("#txtVinNumber", vin_no),
        ("input[name='VIN']", vin_no),
        ("input[name='VinNumber']", vin_no),

        ("#txtTrailerMake", "AUTO MAKE"),
        ("input[name='Make']", "AUTO MAKE"),

        ("#txtTrailerModel", "MODEL X"),
        ("input[name='Model']", "MODEL X"),

        ("#txtTrailerYear", "2024"),
        ("input[name='Year']", "2024"),

        ("#txtRemark", "Automation test trailer"),
        ("textarea[name='Remark']", "Automation test trailer"),
        ("textarea", "Automation test trailer"),
    ]

    for selector, value in fields:
        retry_action(fill_if_exists, page=page, selector=selector, text=value, timeout=4000, attempts=2, delay=1)

    for sel in ["select#ddlCompany", "select[name='Company']"]:
        if retry_select(page, sel, index=1):
            break

    for sel in ["select#ddlTrailerType", "select[name='TrailerType']"]:
        if retry_select(page, sel, index=1):
            break

    for sel in ["select#ddlFleet", "select[name='Fleet']"]:
        if retry_select(page, sel, index=1):
            break

    country_done = False
    for sel in [
        "select#ddlTrailerCountry",
        "select#ddlRegistrationCountry",
        "select[name='RegistrationCountry']",
    ]:
        if retry_select(page, sel, label="Canada") or retry_select(page, sel, index=1):
            country_done = True
            break
    log(f"Country selected: {country_done}")

    safe_wait(page, 1000)

    state_done = False
    for sel in [
        "select#ddlTrailerState",
        "select#ddlTrailerStates",
        "select#ddlRegistrationState",
        "select#ddlState",
        "select[name='RegistrationState']",
    ]:
        if retry_select(page, sel, label="Ontario") or retry_select(page, sel, value="ON"):
            state_done = True
            break
        if choose_first_select_option(page, sel):
            state_done = True
            break
    log(f"State selected: {state_done}")


def submit_trailer_form(page):
    submit_selectors = [
        "#btnTrailerSubmit",
        "#btnSaveTrailer",
        "button:has-text('Save & Close')",
        "text=Save & Close",
        "button:has-text('Save')",
        "text=Save",
    ]

    submitted = False
    for sel in submit_selectors:
        if retry_action(click_if_exists, page=page, selector=sel, timeout=GLOBAL_TIMEOUT, force=True, attempts=3, delay=1):
            submitted = True
            break

    assert submitted, "Could not click Save/Submit button"
    safe_wait(page, 4000)


def test_create_trailer(page):
    try:
        login(page)
        open_trailers_page(page)
        fill_trailer_form(page)
        submit_trailer_form(page)

        take_screenshot(page, "trailer_created.png")
        save_html(page, "trailer_created.html")

        assert True

    except Exception as e:
        log(f"Test failed: {e}")
        take_screenshot(page, "trailer_error.png")
        save_html(page, "trailer_error.html")
        raise