# file name: test_create_carrier.py

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
RETRY_ATTEMPTS = 5
RETRY_DELAY = 2


def random_alpha(n):
    return ''.join(random.choices(string.ascii_letters, k=n))


def random_alphanum(n):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))


def safe_wait(page, ms: int):
    try:
        page.wait_for_timeout(ms)
    except Exception:
        pass


def screenshot(page, name):
    folder = Path("screenshots")
    folder.mkdir(exist_ok=True)
    page.screenshot(path=str(folder / name), full_page=True)


def click_if_exists(page, selector: str, timeout: int = 3000):
    try:
        page.wait_for_selector(selector, timeout=timeout, state="visible")
        loc = page.locator(selector).first
        loc.scroll_into_view_if_needed()
        safe_wait(page, 300)
        loc.click()
        return True
    except Exception:
        pass

    try:
        for frame in page.frames:
            try:
                frame.wait_for_selector(selector, timeout=timeout, state="visible")
                loc = frame.locator(selector).first
                loc.scroll_into_view_if_needed()
                safe_wait(page, 300)
                loc.click()
                return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def click_text_if_exists(page, text_value: str, timeout: int = 3000):
    try:
        loc = page.get_by_text(text_value, exact=True).first
        loc.wait_for(timeout=timeout, state="visible")
        loc.scroll_into_view_if_needed()
        safe_wait(page, 300)
        loc.click()
        return True
    except Exception:
        pass

    try:
        for frame in page.frames:
            try:
                loc = frame.get_by_text(text_value, exact=True).first
                loc.wait_for(timeout=timeout, state="visible")
                loc.scroll_into_view_if_needed()
                safe_wait(page, 300)
                loc.click()
                return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def fill_if_exists(page, selector: str, text: str, timeout: int = 3000):
    try:
        page.wait_for_selector(selector, timeout=timeout, state="visible")
        loc = page.locator(selector).first
        loc.scroll_into_view_if_needed()
        loc.click()
        safe_wait(page, 200)
        loc.fill(text)
        return True
    except Exception:
        return False


def retry_action(fn, attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY, *args, **kwargs):
    for i in range(attempts):
        try:
            ok = fn(*args, **kwargs)
            if ok:
                return True
        except Exception:
            pass

        if i < attempts - 1:
            time.sleep(delay)

    return False


def select2_choose_first(page, container_selector, label="Dropdown"):
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
                        return True
            except Exception:
                continue

        page.keyboard.press("ArrowDown")
        safe_wait(page, 300)
        page.keyboard.press("Enter")
        return True

    except Exception:
        return False


@pytest.fixture(scope="function")
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=150,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        page = browser.new_page()
        page.set_default_timeout(GLOBAL_TIMEOUT)

        yield page

        browser.close()


def test_create_carrier(page):
    try:
        # Open site
        page.goto(BASE_URL, timeout=60000, wait_until="load")
        safe_wait(page, 4000)

        # Login
        assert retry_action(
            fill_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="#txtCorporateId",
            text=CORP_ID,
            timeout=GLOBAL_TIMEOUT,
        ), "Corporate ID field not found"

        assert retry_action(
            fill_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="#txtUserName",
            text=USERNAME,
            timeout=GLOBAL_TIMEOUT,
        ), "Username field not found"

        assert retry_action(
            fill_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="#txtPassword",
            text=PASSWORD,
            timeout=GLOBAL_TIMEOUT,
        ), "Password field not found"

        sign_in_clicked = False
        for sel in ["#signin", "button:has-text('Sign In')", "text=Sign In"]:
            if retry_action(
                click_if_exists,
                attempts=3,
                delay=1,
                page=page,
                selector=sel,
                timeout=GLOBAL_TIMEOUT,
            ):
                sign_in_clicked = True
                break

        assert sign_in_clicked, "Sign In button not found"
        safe_wait(page, 5000)

        # Open C-PANEL
        cpanel_opened = retry_action(
            click_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="a[data-id='#MNU00005']",
            timeout=GLOBAL_TIMEOUT,
        )

        if not cpanel_opened:
            cpanel_opened = retry_action(
                click_if_exists,
                attempts=3,
                delay=1,
                page=page,
                selector="a:has-text('C-PANEL')",
                timeout=GLOBAL_TIMEOUT,
            )

        if not cpanel_opened:
            cpanel_opened = retry_action(
                click_if_exists,
                attempts=3,
                delay=1,
                page=page,
                selector="a:has-text('C Panel')",
                timeout=GLOBAL_TIMEOUT,
            )

        assert cpanel_opened, "C-PANEL menu not found"
        safe_wait(page, 3000)
        screenshot(page, "cpanel_opened.png")

        # Open Carrier
        carrier_opened = retry_action(
            click_text_if_exists,
            attempts=3,
            delay=2,
            page=page,
            text_value="Carrier",
            timeout=5000,
        )

        if not carrier_opened:
            carrier_selectors = [
                "a:has-text('Carrier')",
                "text=Carrier",
                "li:has-text('Carrier')",
                "a[href*='Carrier']",
                "a[href*='carrier']",
            ]

            for sel in carrier_selectors:
                if retry_action(
                    click_if_exists,
                    attempts=3,
                    delay=2,
                    page=page,
                    selector=sel,
                    timeout=5000,
                ):
                    carrier_opened = True
                    break

        assert carrier_opened, "Carrier menu not found after opening C-PANEL"
        safe_wait(page, 4000)
        screenshot(page, "carrier_page_opened.png")

        # Click New
        new_clicked = retry_action(
            click_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="#btnAddCustomerCarrierLocation",
            timeout=5000,
        )

        if not new_clicked:
            for sel in [
                "button:has-text('New')",
                "a:has-text('New')",
                "#btnAddCarrier",
                "#btnAddCustomerCarrierLocation",
                "text=New",
            ]:
                if retry_action(
                    click_if_exists,
                    attempts=3,
                    delay=1,
                    page=page,
                    selector=sel,
                    timeout=5000,
                ):
                    new_clicked = True
                    break

        assert new_clicked, "New button not found on Carrier page"
        safe_wait(page, 2500)
        screenshot(page, "carrier_form_opened.png")

        # Wait for form
        page.wait_for_selector("#txtPrimaryCCLInfoName", timeout=GLOBAL_TIMEOUT, state="visible")

        # Test data
        carrier_name = "AUTO_CARRIER_" + random_alpha(5)
        address = "Toronto Carrier Address " + random_alphanum(5)
        postal_code = "M5V2T6"

        # Fill Name
        assert retry_action(
            fill_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="#txtPrimaryCCLInfoName",
            text=carrier_name,
            timeout=5000,
        ), "Carrier name field not found"

        safe_wait(page, 500)
        page.keyboard.press("Tab")

        # Fill Address
        assert retry_action(
            fill_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="#txtPrimaryCCLInfoAddressOne",
            text=address,
            timeout=5000,
        ), "Address field not found"

        safe_wait(page, 800)
        page.keyboard.press("Tab")

        # State
        retry_action(
            select2_choose_first,
            attempts=3,
            delay=1,
            page=page,
            container_selector="#select2-ddlPrimaryCCLInfoState-container",
            label="State",
        )
        safe_wait(page, 1000)

        # City
        retry_action(
            select2_choose_first,
            attempts=3,
            delay=1,
            page=page,
            container_selector="#select2-ddlCCLinfoCities-container",
            label="City",
        )
        safe_wait(page, 1000)

        # Postal Code
        retry_action(
            fill_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="#txtPrimaryCCLInfoPostalCode",
            text=postal_code,
            timeout=5000,
        )
        safe_wait(page, 500)
        page.keyboard.press("Tab")
        safe_wait(page, 1000)

        # Save
        save_clicked = retry_action(
            click_if_exists,
            attempts=3,
            delay=1,
            page=page,
            selector="#btnCustomerSubmit",
            timeout=5000,
        )

        if not save_clicked:
            for sel in [
                "#btnCarrierSubmit",
                "#btnCustomerSubmit",
                "button:has-text('Save & Close')",
                "button:has-text('Save')",
                "text=Save & Close",
                "text=Save",
            ]:
                if retry_action(
                    click_if_exists,
                    attempts=3,
                    delay=1,
                    page=page,
                    selector=sel,
                    timeout=5000,
                ):
                    save_clicked = True
                    break

        assert save_clicked, "Save button not found"
        safe_wait(page, 5000)
        screenshot(page, "carrier_created.png")

    except Exception:
        screenshot(page, "carrier_create_error.png")
        raise