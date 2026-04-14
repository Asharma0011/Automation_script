from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import random
import string
import time
from pathlib import Path

LOG_PATH = Path(__file__).parent / "trailers.log"

GLOBAL_TIMEOUT = 20000  # ms
NAV_TIMEOUT = 60000
RETRY_ATTEMPTS = 5
RETRY_DELAY = 2  # seconds


def _log(msg):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def random_alpha(n):
    return "".join(random.choices(string.ascii_letters, k=n))


def random_alphanum(n):
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def _screenshot(page, name):
    path = Path(__file__).parent / name
    _log(f"Saving screenshot to {path}")
    try:
        page.screenshot(path=str(path), full_page=True)
        _log("Screenshot saved")
    except Exception as e:
        _log(f"Screenshot failed: {e}")


def save_html(page, name):
    path = Path(__file__).parent / name
    try:
        path.write_text(page.content(), encoding="utf-8")
        _log(f"Saved HTML to {path}")
    except Exception as e:
        _log(f"Failed to save HTML {name}: {e}")


def safe_wait(page, ms: int):
    try:
        page.wait_for_timeout(ms)
    except Exception as e:
        _log(f"safe_wait ignored error: {e}")


def retry_action(fn, attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY, *args, **kwargs):
    last_error = None
    for i in range(attempts):
        try:
            ok = fn(*args, **kwargs)
            if ok:
                return True
        except Exception as e:
            last_error = e
            _log(f"retry_action attempt {i + 1} failed: {e}")
        if i < attempts - 1:
            time.sleep(delay)
    if last_error:
        _log(f"retry_action exhausted retries. Last error: {last_error}")
    return False


def _try_click_in_context(ctx, selector: str, timeout: int = 3000, force=False):
    locator = ctx.locator(selector).first
    if locator.count() == 0:
        return False
    locator.wait_for(state="visible", timeout=timeout)
    locator.scroll_into_view_if_needed()
    locator.click(timeout=timeout, force=force)
    return True


def click_if_exists(page, selector: str, timeout: int = 3000, force=False):
    """Click visible element on page or frames."""
    try:
        if _try_click_in_context(page, selector, timeout=timeout, force=force):
            _log(f"Clicked {selector} on main page")
            return True
    except Exception as e:
        _log(f"Main page click failed for {selector}: {e}")

    try:
        for f in page.frames:
            try:
                if _try_click_in_context(f, selector, timeout=timeout, force=force):
                    _log(f"Clicked {selector} in frame {f.name or '<unnamed>'}")
                    return True
            except Exception as e:
                _log(f"Frame click failed for {selector} in frame {f.name or '<unnamed>'}: {e}")
    except Exception as e:
        _log(f"click_if_exists frame scan failed: {e}")

    _log(f"click_if_exists: {selector} not found/visible on page or frames")
    return False


def _try_fill_in_context(ctx, selector: str, text: str, timeout: int = 3000):
    locator = ctx.locator(selector).first
    if locator.count() == 0:
        return False
    locator.wait_for(state="visible", timeout=timeout)
    locator.fill(text, timeout=timeout)
    return True


def fill_if_exists(page, selector: str, text: str, timeout: int = 3000):
    try:
        if _try_fill_in_context(page, selector, text, timeout=timeout):
            _log(f"Filled {selector} with {text} on main page")
            return True
    except Exception as e:
        _log(f"Main page fill failed for {selector}: {e}")

    try:
        for f in page.frames:
            try:
                if _try_fill_in_context(f, selector, text, timeout=timeout):
                    _log(f"Filled {selector} with {text} in frame {f.name or '<unnamed>'}")
                    return True
            except Exception as e:
                _log(f"Frame fill failed for {selector} in frame {f.name or '<unnamed>'}: {e}")
    except Exception as e:
        _log(f"fill_if_exists frame scan failed: {e}")

    _log(f"fill_if_exists: {selector} not found/visible on page or frames")
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
                _log(f"Selected option on {selector} {kwargs} on main page")
                return True
        except Exception as e:
            _log(f"retry_select main page attempt {i+1} failed for {selector}: {e}")

        try:
            for f in page.frames:
                try:
                    if _try_select_in_context(f, selector, **kwargs):
                        _log(f"Selected option on {selector} {kwargs} in frame {f.name or '<unnamed>'}")
                        return True
                except Exception as e:
                    _log(f"retry_select frame attempt {i+1} failed for {selector}: {e}")
        except Exception as e:
            _log(f"retry_select frame scan failed: {e}")

        time.sleep(RETRY_DELAY)
    return False


def eval_on_selector_all_anywhere(page, selector, script):
    try:
        if page.locator(selector).count() > 0:
            return page.eval_on_selector_all(selector, script)
    except Exception:
        pass

    for f in page.frames:
        try:
            if f.locator(selector).count() > 0:
                return f.eval_on_selector_all(selector, script)
        except Exception:
            continue
    return []


def choose_first_select_option(page, selector):
    try:
        opts = eval_on_selector_all_anywhere(
            page,
            selector + " option",
            "els => els.map(e => ({v: e.value, t: e.textContent, d: e.disabled, s: e.selected}))"
        )
        for o in opts:
            v = o.get("v")
            txt = (o.get("t") or "").strip().lower()
            if v and str(v).strip() not in ["", "0", "-1"] and not o.get("d") and txt != "select":
                if retry_select(page, selector, value=v):
                    return v
    except Exception as e:
        _log(f"choose_first_select_option failed for {selector}: {e}")
    return None


def select_dropdown_by_label_fallback(page, label_text, option_text=None):
    """Find label, then nearest select on page or frames."""
    contexts = [page] + list(page.frames)

    for ctx in contexts:
        try:
            label = ctx.locator(f"label:has-text('{label_text}')").first
            if label.count() == 0:
                continue

            parent = label.locator("xpath=..")
            select_locator = parent.locator("select").first

            if select_locator.count() == 0:
                # try broader nearby search
                select_locator = parent.locator("xpath=.//following::select[1]").first

            if select_locator.count() == 0:
                continue

            select_locator.wait_for(state="visible", timeout=4000)

            if option_text:
                try:
                    select_locator.select_option(label=option_text)
                    _log(f"Selected '{option_text}' for label '{label_text}'")
                    return True
                except Exception as e:
                    _log(f"Label fallback exact option failed for '{label_text}': {e}")

            try:
                select_locator.select_option(index=1)
                _log(f"Selected first option for label '{label_text}'")
                return True
            except Exception as e:
                _log(f"Label fallback index select failed for '{label_text}': {e}")

        except Exception as e:
            _log(f"select_dropdown_by_label_fallback failed for {label_text}: {e}")

    return False


def wait_for_any_visible(page, selectors, timeout_each=5000):
    """Wait until any selector is visible on page or frames."""
    for sel in selectors:
        try:
            if page.locator(sel).first.is_visible(timeout=timeout_each):
                _log(f"Visible on main page: {sel}")
                return ("page", sel)
        except Exception:
            pass

        for f in page.frames:
            try:
                if f.locator(sel).first.is_visible(timeout=timeout_each):
                    _log(f"Visible in frame {f.name or '<unnamed>'}: {sel}")
                    return (f, sel)
            except Exception:
                continue
    return (None, None)


def wait_for_url_change_or_content(page, expected_selectors, timeout_ms=15000):
    start = time.time()
    start_url = page.url
    while (time.time() - start) * 1000 < timeout_ms:
        if page.url != start_url:
            _log(f"URL changed from {start_url} to {page.url}")
            return True

        ctx, sel = wait_for_any_visible(page, expected_selectors, timeout_each=1000)
        if ctx:
            _log(f"Detected page/content ready via selector {sel}")
            return True

        safe_wait(page, 500)

    _log("No URL/content change detected within timeout")
    return False


with sync_playwright() as p:
    browser = None
    try:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
            slow_mo=150
        )

        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        _log("Navigating to site...")
        try:
            page.goto("https://afm2020.com/", timeout=NAV_TIMEOUT, wait_until="load")
        except Exception as e:
            _log(f"Initial goto failed: {e}; retrying once")
            page.goto("https://afm2020.com/", timeout=NAV_TIMEOUT)

        safe_wait(page, 3000)
        _log(f"Landed on URL: {page.url}")

        # LOGIN
        _log("Filling login form...")
        retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtCorporateId", text="AFMDEMO", timeout=GLOBAL_TIMEOUT)
        retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtUserName", text="Asharma", timeout=GLOBAL_TIMEOUT)
        retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtPassword", text="Avaal@123", timeout=GLOBAL_TIMEOUT)

        clicked = False
        for sel in ["#signin", "button:has-text('Sign In')", "text=Sign In"]:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=GLOBAL_TIMEOUT, force=True):
                clicked = True
                break

        if not clicked:
            raise Exception("Could not click sign-in selector")

        safe_wait(page, 5000)
        _log(f"Login step completed. Current URL: {page.url}")

        # OPEN C PANEL
        _log("Opening C-PANEL...")
        cpanel_clicked = False
        for sel in [
            "a[data-id='#MNU00005']",
            "a:has-text('C-PANEL')",
            "a:has-text('C Panel')",
            "text=C-PANEL",
            "text=C Panel"
        ]:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=GLOBAL_TIMEOUT, force=True):
                cpanel_clicked = True
                _log(f"C-PANEL clicked using selector: {sel}")
                break

        if not cpanel_clicked:
            _log("C-PANEL click failed; continuing with broad trailer navigation selectors")

        safe_wait(page, 2000)

        # OPEN TRAILERS PAGE
        _log("Opening Trailers page...")
        trailer_menu_clicked = False
        trailer_menu_selectors = [
            "#MNU00005 a:has-text('Trailers')",
            "a[href*='Masters/Trailer/TrailerList']",
            "a[href*='Trailer/TrailerList']",
            "a:has-text('Trailers')",
            "text=Trailers"
        ]

        for sel in trailer_menu_selectors:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=GLOBAL_TIMEOUT, force=True):
                trailer_menu_clicked = True
                _log(f"Trailer menu clicked using selector: {sel}")
                break

        if not trailer_menu_clicked:
            _screenshot(page, "trailers_menu_not_clicked.png")
            save_html(page, "trailers_menu_not_clicked.html")
            raise Exception("Could not click Trailers menu")

        # Wait for actual trailers page content instead of fixed sleep only
        trailers_ready_selectors = [
            "#btnAddTrailer",
            "#btnAddNewTrailer",
            "a:has-text('New')",
            "button:has-text('New')",
            "[title='New']",
            "[aria-label='New']",
            "text=+ New",
            "text=New",
            "table",
            ".dataTables_wrapper",
            ".grid"
        ]

        wait_for_url_change_or_content(page, trailers_ready_selectors, timeout_ms=20000)
        safe_wait(page, 1500)
        _log(f"After trailer navigation URL: {page.url}")

        # CLICK NEW BUTTON
        _log("Trying to click New button...")
        add_clicked = False
        add_trailer_selectors = [
            "#btnAddTrailer",
            "#btnAddNewTrailer",
            "a:has-text('New')",
            "button:has-text('New')",
            "[title='New']",
            "[aria-label='New']",
            "text=+ New",
            "text=New"
        ]

        for sel in add_trailer_selectors:
            if retry_action(click_if_exists, attempts=2, delay=1, page=page, selector=sel, timeout=5000, force=True):
                add_clicked = True
                _log(f"Add Trailer clicked using selector: {sel}")
                break

        if not add_clicked:
            _screenshot(page, "new_button_not_clicked.png")
            save_html(page, "new_button_not_clicked.html")
            raise Exception("New button not found or not clickable")

        safe_wait(page, 2000)

        # WAIT FOR CREATE TRAILER MODAL
        _log("Waiting for Create Trailer modal/form...")
        modal_found = False
        modal_selectors = [
            "#myTrailerModal",
            ".modal.show",
            ".modal.in",
            "text=Create Trailer",
            "input[name='TrailerNo']",
            "#txtTrailerNumber",
            "#txtTrailerNo"
        ]

        ctx, found_sel = wait_for_any_visible(page, modal_selectors, timeout_each=8000)
        if ctx:
            modal_found = True
            _log(f"Trailer modal/form visible using selector: {found_sel}")

        if not modal_found:
            _screenshot(page, "trailer_modal_not_found.png")
            save_html(page, "trailer_after_add.html")
            raise Exception("Trailer modal/form did not appear after clicking New")

        # TEST DATA
        trailer_no = "TRL" + random_alphanum(5).upper()
        plate_no = random_alphanum(6).upper()
        vin_no = random_alphanum(17).upper()

        _log(f"Generated trailer_no={trailer_no}, plate_no={plate_no}, vin_no={vin_no}")

        # FILL TEXT FIELDS
        text_field_candidates = [
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
            ("textarea", "Automation test trailer")
        ]

        for selector, value in text_field_candidates:
            retry_action(fill_if_exists, attempts=2, delay=1, page=page, selector=selector, text=value, timeout=4000)

        # SELECT COMPANY
        for sel in [
            "select#ddlCompany",
            "select[name='Company']"
        ]:
            if retry_select(page, sel, index=1):
                _log(f"Company selected using {sel}")
                break

        # SELECT TRAILER TYPE
        trailer_type_done = False
        for sel in [
            "select#ddlTrailerType",
            "select[name='TrailerType']"
        ]:
            if retry_select(page, sel, index=1):
                _log(f"Trailer Type selected using {sel}")
                trailer_type_done = True
                break

        if not trailer_type_done:
            trailer_type_done = select_dropdown_by_label_fallback(page, "Trailer Type")

        # SELECT FLEET
        for sel in [
            "select#ddlFleet",
            "select[name='Fleet']"
        ]:
            if retry_select(page, sel, index=1):
                _log(f"Fleet selected using {sel}")
                break

        # REGISTRATION COUNTRY
        country_done = False
        for sel in [
            "select#ddlTrailerCountry",
            "select#ddlRegistrationCountry",
            "select[name='RegistrationCountry']"
        ]:
            if retry_select(page, sel, label="Canada"):
                _log(f"Registration Country selected as Canada using {sel}")
                country_done = True
                break
            if retry_select(page, sel, index=1):
                _log(f"Registration Country selected using first option on {sel}")
                country_done = True
                break

        if not country_done:
            country_done = select_dropdown_by_label_fallback(page, "Registration Country", "Canada")

        safe_wait(page, 1000)

        # REGISTRATION STATE / PROVINCE
        state_done = False
        for sel in [
            "select#ddlTrailerState",
            "select#ddlTrailerStates",
            "select#ddlRegistrationState",
            "select#ddlState",
            "select[name='RegistrationState']"
        ]:
            if retry_select(page, sel, label="Ontario"):
                _log(f"Registration State selected as Ontario using {sel}")
                state_done = True
                break

            if retry_select(page, sel, value="ON"):
                _log(f"Registration State selected as ON using {sel}")
                state_done = True
                break

            v = choose_first_select_option(page, sel)
            if v:
                _log(f"Registration State selected using first valid option on {sel}, value={v}")
                state_done = True
                break

        if not state_done:
            state_done = select_dropdown_by_label_fallback(page, "Registration State / Province", "Ontario")

        safe_wait(page, 1500)

        # SUBMIT USING SAVE & CLOSE
        _log("Trying to submit trailer form...")
        submitted = False
        submit_selectors = [
            "#btnTrailerSubmit",
            "#btnSaveTrailer",
            "button:has-text('Save & Close')",
            "text=Save & Close",
            "button:has-text('Save')",
            "text=Save"
        ]

        for sel in submit_selectors:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=GLOBAL_TIMEOUT, force=True):
                submitted = True
                _log(f"Trailer submit clicked using selector: {sel}")
                break

        if not submitted:
            _screenshot(page, "trailer_submit_not_clicked.png")
            save_html(page, "trailer_submit_not_clicked.html")
            raise Exception("Could not find submit button for Trailer")

        safe_wait(page, 4000)
        _screenshot(page, "trailer_created.png")
        save_html(page, "trailer_created.html")
        _log("Trailer created flow completed (or attempted successfully)")

    except Exception as e:
        _log(f"Unhandled error during Trailers script: {e}")
        try:
            if "page" in locals():
                _screenshot(page, "trailer_error.png")
                save_html(page, "trailer_error.html")
        except Exception:
            pass
        raise
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass