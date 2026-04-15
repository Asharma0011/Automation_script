
from playwright.sync_api import sync_playwright
import random
import string
import time
from pathlib import Path

LOG_PATH = Path(__file__).parent / "factoring_company_create.log"
GLOBAL_TIMEOUT = 20000
RETRY_ATTEMPTS = 5
RETRY_DELAY = 2


def _log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def random_alpha(n):
    return ''.join(random.choices(string.ascii_letters, k=n))


def random_alphanum(n):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))


def _screenshot(page, name):
    path = Path(__file__).parent / name
    _log(f"Saving screenshot to {path}")
    print(f"Saving screenshot to {path}")
    try:
        page.screenshot(path=str(path), full_page=True)
        _log("Screenshot saved")
        print("Screenshot saved")
    except Exception as e:
        _log(f"Screenshot failed: {e}")
        print("Screenshot failed:", e)


def safe_wait(page, ms: int):
    try:
        page.wait_for_timeout(ms)
    except Exception as e:
        _log(f"safe_wait ignored error: {e}")


def click_if_exists(page, selector: str, timeout: int = 3000):
    try:
        page.wait_for_selector(selector, timeout=timeout, state="visible")
        page.locator(selector).first.click()
        _log(f"Clicked {selector} on main page")
        return True
    except Exception:
        pass

    try:
        for f in page.frames:
            try:
                f.wait_for_selector(selector, timeout=timeout, state="visible")
                f.locator(selector).first.click()
                _log(f"Clicked {selector} in frame {f.name}")
                return True
            except Exception:
                continue
    except Exception as e:
        _log(f"click_if_exists frame scan failed: {e}")

    _log(f"click_if_exists: {selector} not found")
    return False


def fill_if_exists(page, selector: str, text: str, timeout: int = 3000):
    try:
        page.wait_for_selector(selector, timeout=timeout, state="visible")
        loc = page.locator(selector).first
        loc.click()
        safe_wait(page, 200)
        loc.fill(text)
        _log(f"Filled {selector} with {text}")
        return True
    except Exception as e:
        _log(f"fill_if_exists failed for {selector}: {e}")
    return False


def retry_action(fn, attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY, *args, **kwargs):
    for i in range(attempts):
        try:
            ok = fn(*args, **kwargs)
            if ok:
                return True
        except Exception as e:
            _log(f"retry_action exception: {e}")
        if i < attempts - 1:
            time.sleep(delay)
    return False


def select2_choose_first(page, container_selector, label):
    try:
        page.wait_for_selector(container_selector, timeout=4000, state="visible")
        page.locator(container_selector).first.click()
        safe_wait(page, 1000)

        option_selectors = [
            ".select2-results__option:not([aria-disabled='true'])",
            ".select2-results li",
        ]

        for sel in option_selectors:
            try:
                page.wait_for_selector(sel, timeout=3000)
                opts = page.locator(sel)
                count = opts.count()
                for i in range(count):
                    txt = opts.nth(i).inner_text().strip()
                    if txt and txt.lower() not in ["select", "searching..."]:
                        opts.nth(i).click()
                        _log(f"{label} selected: {txt}")
                        return True
            except Exception:
                continue

        page.keyboard.press("ArrowDown")
        safe_wait(page, 300)
        page.keyboard.press("Enter")
        _log(f"{label} selected by keyboard")
        return True

    except Exception as e:
        _log(f"select2_choose_first failed for {label}: {e}")
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
        page = browser.new_page()

        # OPEN SITE
        page.goto("https://afm2020.com/", timeout=60000, wait_until="load")
        safe_wait(page, 4000)

        # LOGIN
        retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtCorporateId", text="AFMDEMO", timeout=GLOBAL_TIMEOUT)
        retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtUserName", text="Asharma", timeout=GLOBAL_TIMEOUT)
        retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtPassword", text="Avaal@123", timeout=GLOBAL_TIMEOUT)

        for sel in ["#signin", "button:has-text('Sign In')", "text=Sign In"]:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=GLOBAL_TIMEOUT):
                break

        safe_wait(page, 5000)

        # OPEN C-PANEL
        if not retry_action(click_if_exists, attempts=3, delay=1, page=page, selector="a[data-id='#MNU00005']", timeout=GLOBAL_TIMEOUT):
            retry_action(click_if_exists, attempts=3, delay=1, page=page, selector="a:has-text('C-PANEL')", timeout=GLOBAL_TIMEOUT)
            retry_action(click_if_exists, attempts=3, delay=1, page=page, selector="a:has-text('C Panel')", timeout=GLOBAL_TIMEOUT)

        safe_wait(page, 2000)

        # OPEN FACTORING COMPANIES
        for sel in [
            "#MNU00005 a:has-text('Factoring Companies')",
            "a[href*='FactoringCompany']",
            "a[href*='FactoringCompanies']",
            "a:has-text('Factoring Companies')",
            "text=Factoring Companies",
        ]:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=GLOBAL_TIMEOUT):
                _log(f"Opened Factoring Companies using {sel}")
                break

        safe_wait(page, 3000)

        # CLICK NEW
        for sel in [
            "#btnAddFactoringCompany",
            "#btnAddFactorCompany",
            "button:has-text('New')",
            "button:has-text('Add New')",
        ]:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=5000):
                _log(f"Clicked New using {sel}")
                break
        else:
            raise Exception("New button not found for Factoring Company")

        safe_wait(page, 2500)

        # WAIT FOR FORM
        page.wait_for_selector("#txtFactoringCompanyName", timeout=GLOBAL_TIMEOUT, state="visible")
        _log("Factoring Company create form opened")

        # TEST DATA
        factoring_company_name = "AUTO_FACTOR_" + random_alpha(5)
        address = "Toronto Test Address " + random_alphanum(5)
        postal_code = "M5V2T6"

        # NAME (Mandatory)
        if not retry_action(
            fill_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="#txtFactoringCompanyName",
            text=factoring_company_name,
            timeout=5000
        ):
            raise Exception("Factoring Company Name field not found")

        safe_wait(page, 500)

        # COMPANY (Mandatory - keep existing selected value if already auto-populated)
        try:
            page.wait_for_selector("#ddlFactoringCompanyCompany", timeout=3000, state="visible")
            current_value = page.locator("#ddlFactoringCompanyCompany").input_value()
            if not current_value:
                page.locator("#ddlFactoringCompanyCompany").select_option(index=1)
                _log("Company selected using index 1")
            else:
                _log(f"Company already selected: {current_value}")
        except Exception as e:
            _log(f"Company selection skipped/failed: {e}")

        safe_wait(page, 500)

        # ADDRESS (Mandatory)
        if not retry_action(
            fill_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="#txtFactoringCompanyAddress1",
            text=address,
            timeout=5000
        ):
            raise Exception("Address field not found")

        safe_wait(page, 500)

        # COUNTRY (Mandatory - select Canada if needed)
        try:
            page.wait_for_selector("#ddlFactoringCompanyCountry", timeout=3000, state="visible")
            current_country = page.locator("#ddlFactoringCompanyCountry").input_value()
            if not current_country:
                page.locator("#ddlFactoringCompanyCountry").select_option(label="Canada")
                _log("Country selected: Canada")
            else:
                _log(f"Country already selected: {current_country}")
        except Exception as e:
            _log(f"Country selection skipped/failed: {e}")

        safe_wait(page, 500)

        # STATE (Mandatory)
        if not retry_action(
            select2_choose_first,
            attempts=3,
            delay=1,
            page=page,
            container_selector="#select2-ddlFactoringCompanyStates-container",
            label="State"
        ):
            raise Exception("State dropdown not found or not selected")

        safe_wait(page, 1000)

        # CITY (Mandatory)
        if not retry_action(
            select2_choose_first,
            attempts=3,
            delay=1,
            page=page,
            container_selector="#select2-ddlFactoringCompanyCities-container",
            label="City"
        ):
            raise Exception("City dropdown not found or not selected")

        safe_wait(page, 1000)

        # POSTAL CODE (Mandatory)
        if not retry_action(
            fill_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="#txtFactoringCompanyZipCode",
            text=postal_code,
            timeout=5000
        ):
            raise Exception("Postal Code field not found")

        safe_wait(page, 1000)

        # OPTIONAL FIELDS - only fill if you need them later
        # retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtFactoringCompanyEmail", text="test@example.com", timeout=5000)
        # retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtFactoringCompanyPhone2", text="(111) 111-1111", timeout=5000)

        # SAVE
        for sel in [
            "#btnFactoringCompanySubmit",
            "button:has-text('Save')",
            "button:has-text('Save & New')",
            "text=Save",
        ]:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=5000):
                _log(f"Clicked save using {sel}")
                break
        else:
            raise Exception("Save button not found for Factoring Company")

        safe_wait(page, 5000)

        _screenshot(page, "factoring_company_created.png")
        _log("Factoring Company creation attempted")
        print("Factoring Company creation attempted")

    except Exception as e:
        _log(f"Unhandled error during factoring company create script: {e}")
        print("Unhandled error during factoring company create script:", e)
        try:
            if "page" in locals():
                _screenshot(page, "factoring_company_create_error.png")
                html_path = Path(__file__).parent / "factoring_company_create_error.html"
                html_path.write_text(page.content(), encoding="utf-8")
        except Exception:
            pass
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass