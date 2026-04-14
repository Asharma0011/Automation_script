from playwright.sync_api import sync_playwright
import random
import string
import time
from pathlib import Path

LOG_PATH = Path(__file__).parent / "vendors_create.log"
GLOBAL_TIMEOUT = 20000
RETRY_ATTEMPTS = 5
RETRY_DELAY = 2

# Update these as needed
BASE_URL = "https://afm2020.com/"
CORPORATE_ID = "AFMDEMO"
USERNAME = "Asharma"
PASSWORD = "Avaal@123"


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
        page.goto(BASE_URL, timeout=60000, wait_until="load")
        safe_wait(page, 4000)

        # LOGIN
        retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtCorporateId", text=CORPORATE_ID, timeout=GLOBAL_TIMEOUT)
        retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtUserName", text=USERNAME, timeout=GLOBAL_TIMEOUT)
        retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtPassword", text=PASSWORD, timeout=GLOBAL_TIMEOUT)

        for sel in ["#signin", "button:has-text('Sign In')", "text=Sign In"]:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=GLOBAL_TIMEOUT):
                break

        safe_wait(page, 5000)

        # OPEN C-PANEL
        if not retry_action(click_if_exists, attempts=3, delay=1, page=page, selector="a[data-id='#MNU00005']", timeout=GLOBAL_TIMEOUT):
            retry_action(click_if_exists, attempts=3, delay=1, page=page, selector="a:has-text('C-PANEL')", timeout=GLOBAL_TIMEOUT)
            retry_action(click_if_exists, attempts=3, delay=1, page=page, selector="a:has-text('C Panel')", timeout=GLOBAL_TIMEOUT)

        safe_wait(page, 2000)

        # OPEN VENDORS
        vendor_menu_selectors = [
            "#MNU00005 a:has-text('Vendors')",
            "a[href*='Vendor']",
            "a[href*='Vendors']",
            "a[href*='VendorList']",
            "a:has-text('Vendors')",
            "text=Vendors",
        ]

        opened_vendors = False
        for sel in vendor_menu_selectors:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=GLOBAL_TIMEOUT):
                _log(f"Opened Vendors using {sel}")
                opened_vendors = True
                break

        if not opened_vendors:
            raise Exception("Vendors menu not found")

        safe_wait(page, 3000)

        # CLICK NEW
        new_button_selectors = [
            "#btnAddVendor",
            "#btnAddVendorCarrierLocation",
            "#btnAddCustomerCarrierLocation",
            "button:has-text('New')",
            "button:has-text('Add Vendor')",
            "button:has-text('Create Vendor')",
            "text=New",
        ]

        clicked_new = False
        for sel in new_button_selectors:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=5000):
                _log(f"Clicked New using {sel}")
                clicked_new = True
                break

        if not clicked_new:
            raise Exception("New Vendor button not found")

        safe_wait(page, 2500)

        # WAIT FOR FORM
        form_selectors = [
            "#txtPrimaryCCLInfoName",
            "#txtVendorName",
            "#txtPrimaryVendorName",
            "input[name*='VendorName']",
        ]

        vendor_name_field = None
        for sel in form_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000, state="visible")
                vendor_name_field = sel
                _log(f"Vendor create form opened with field {sel}")
                break
            except Exception:
                continue

        if not vendor_name_field:
            raise Exception("Vendor create form did not open")

        # TEST DATA
        vendor_name = "AUTO_VENDOR_" + random_alpha(5)
        address = "Toronto Vendor Address " + random_alphanum(5)
        postal_code = "M5V2T6"

        # NAME
        if not retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector=vendor_name_field, text=vendor_name, timeout=5000):
            raise Exception("Vendor name field not found")

        safe_wait(page, 500)
        page.keyboard.press("Tab")

        # ADDRESS
        address_selectors = [
            "#txtPrimaryCCLInfoAddressOne",
            "#txtVendorAddressOne",
            "#txtPrimaryVendorAddressOne",
            "input[name*='AddressOne']",
        ]

        address_filled = False
        for sel in address_selectors:
            if retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector=sel, text=address, timeout=5000):
                address_filled = True
                break

        if not address_filled:
            raise Exception("Vendor address field not found")

        safe_wait(page, 800)
        page.keyboard.press("Tab")

        # STATE
        state_selectors = [
            "#select2-ddlPrimaryCCLInfoState-container",
            "#select2-ddlVendorState-container",
            "#select2-ddlPrimaryVendorState-container",
        ]

        for sel in state_selectors:
            if retry_action(
                select2_choose_first,
                attempts=3,
                delay=1,
                page=page,
                container_selector=sel,
                label="State"
            ):
                break

        safe_wait(page, 1000)

        # CITY
        city_selectors = [
            "#select2-ddlCCLinfoCities-container",
            "#select2-ddlVendorCity-container",
            "#select2-ddlPrimaryVendorCity-container",
        ]

        for sel in city_selectors:
            if retry_action(
                select2_choose_first,
                attempts=3,
                delay=1,
                page=page,
                container_selector=sel,
                label="City"
            ):
                break

        safe_wait(page, 1000)

        # POSTAL CODE
        postal_selectors = [
            "#txtPrimaryCCLInfoPostalCode",
            "#txtVendorPostalCode",
            "#txtPrimaryVendorPostalCode",
            "input[name*='PostalCode']",
        ]

        for sel in postal_selectors:
            if retry_action(
                fill_if_exists,
                attempts=3,
                delay=1,
                page=page,
                selector=sel,
                text=postal_code,
                timeout=5000
            ):
                break

        safe_wait(page, 500)
        page.keyboard.press("Tab")
        safe_wait(page, 1000)

        # SAVE & CLOSE
        save_selectors = [
            "#btnVendorSubmit",
            "#btnVendorSave",
            "#btnCustomerSubmit",
            "button:has-text('Save & Close')",
            "button:has-text('Save')",
            "text=Save & Close",
        ]

        saved = False
        for sel in save_selectors:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=5000):
                _log(f"Clicked save using {sel}")
                saved = True
                break

        if not saved:
            raise Exception("Vendor save button not found")

        safe_wait(page, 5000)

        _screenshot(page, "vendor_created.png")
        _log("Vendor creation attempted")
        print("Vendor creation attempted")

    except Exception as e:
        _log(f"Unhandled error during vendor create script: {e}")
        print("Unhandled error during vendor create script:", e)
        try:
            if "page" in locals():
                _screenshot(page, "vendor_create_error.png")
                html_path = Path(__file__).parent / "vendor_create_error.html"
                html_path.write_text(page.content(), encoding="utf-8")
        except Exception:
            pass
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass