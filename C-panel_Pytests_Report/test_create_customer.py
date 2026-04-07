import random
import string
import time
from pathlib import Path

import allure
import pytest
from playwright.sync_api import sync_playwright

LOG_PATH = Path(__file__).parent / "customers_create.log"
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


def attach_screenshot(page, name="screenshot"):
    try:
        screenshot_bytes = page.screenshot(full_page=True)
        allure.attach(
            screenshot_bytes,
            name=name,
            attachment_type=allure.attachment_type.PNG
        )
    except Exception as e:
        _log(f"Screenshot attach failed: {e}")


def attach_text_file(file_path, attachment_name):
    path = Path(file_path)
    if path.exists():
        allure.attach(
            path.read_text(encoding="utf-8", errors="ignore"),
            name=attachment_name,
            attachment_type=allure.attachment_type.TEXT
        )


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


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
            slow_mo=150
        )
        page = browser.new_page()
        yield page
        browser.close()


@allure.epic("AFM Application")
@allure.feature("Customer Management")
@allure.story("Create Customer")
@allure.severity(allure.severity_level.CRITICAL)
@allure.title("Verify user can create a new customer")
def test_create_customer(page):
    customer_name = "AUTO_CUST_" + random_alpha(5)
    address = "Toronto Test Address " + random_alphanum(5)
    postal_code = "M5V2T6"

    allure.dynamic.description(
        f"Test creates a customer with name: {customer_name}, "
        f"address: {address}, postal code: {postal_code}"
    )

    try:
        with allure.step("Open AFM website"):
            page.goto("https://afm2020.com/", timeout=60000, wait_until="load")
            safe_wait(page, 4000)
            attach_screenshot(page, "Website Opened")

        with allure.step("Login into application"):
            assert retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtCorporateId",
                                text="AFMDEMO", timeout=GLOBAL_TIMEOUT), "Corporate ID field not found"
            assert retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtUserName",
                                text="Asharma", timeout=GLOBAL_TIMEOUT), "Username field not found"
            assert retry_action(fill_if_exists, attempts=3, delay=1, page=page, selector="#txtPassword",
                                text="Avaal@123", timeout=GLOBAL_TIMEOUT), "Password field not found"

            login_clicked = False
            for sel in ["#signin", "button:has-text('Sign In')", "text=Sign In"]:
                if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=GLOBAL_TIMEOUT):
                    login_clicked = True
                    break

            assert login_clicked, "Sign In button not found"
            safe_wait(page, 5000)
            attach_screenshot(page, "Logged In")

        with allure.step("Open C-PANEL"):
            opened = retry_action(click_if_exists, attempts=3, delay=1, page=page,
                                  selector="a[data-id='#MNU00005']", timeout=GLOBAL_TIMEOUT)

            if not opened:
                retry_action(click_if_exists, attempts=3, delay=1, page=page,
                             selector="a:has-text('C-PANEL')", timeout=GLOBAL_TIMEOUT)
                retry_action(click_if_exists, attempts=3, delay=1, page=page,
                             selector="a:has-text('C Panel')", timeout=GLOBAL_TIMEOUT)

            safe_wait(page, 2000)
            attach_screenshot(page, "C-Panel Opened")

        with allure.step("Open Customers page"):
            opened_customers = False
            for sel in [
                "#MNU00005 a:has-text('Customers')",
                "a[href*='Customer']",
                "a[href*='Customers']",
                "a[href*='CustomerList']",
                "a:has-text('Customers')",
                "text=Customers",
            ]:
                if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=GLOBAL_TIMEOUT):
                    _log(f"Opened Customers using {sel}")
                    opened_customers = True
                    break

            assert opened_customers, "Customers menu not found"
            safe_wait(page, 3000)
            attach_screenshot(page, "Customers Page Opened")

        with allure.step("Click New button"):
            assert retry_action(click_if_exists, attempts=3, delay=1, page=page,
                                selector="#btnAddCustomerCarrierLocation", timeout=5000), \
                "New button not found: #btnAddCustomerCarrierLocation"

            safe_wait(page, 2500)
            page.wait_for_selector("#txtPrimaryCCLInfoName", timeout=GLOBAL_TIMEOUT, state="visible")
            _log("Customer create form opened")
            attach_screenshot(page, "Customer Form Opened")

        with allure.step("Fill customer details"):
            assert retry_action(fill_if_exists, attempts=3, delay=1, page=page,
                                selector="#txtPrimaryCCLInfoName", text=customer_name, timeout=5000), \
                "Customer name field not found"
            safe_wait(page, 500)
            page.keyboard.press("Tab")

            assert retry_action(fill_if_exists, attempts=3, delay=1, page=page,
                                selector="#txtPrimaryCCLInfoAddressOne", text=address, timeout=5000), \
                "Address field not found"
            safe_wait(page, 800)
            page.keyboard.press("Tab")

            retry_action(
                select2_choose_first,
                attempts=3,
                delay=1,
                page=page,
                container_selector="#select2-ddlPrimaryCCLInfoState-container",
                label="State"
            )
            safe_wait(page, 1000)

            retry_action(
                select2_choose_first,
                attempts=3,
                delay=1,
                page=page,
                container_selector="#select2-ddlCCLinfoCities-container",
                label="City"
            )
            safe_wait(page, 1000)

            retry_action(
                fill_if_exists,
                attempts=3,
                delay=1,
                page=page,
                selector="#txtPrimaryCCLInfoPostalCode",
                text=postal_code,
                timeout=5000
            )
            safe_wait(page, 500)
            page.keyboard.press("Tab")
            safe_wait(page, 1000)

            attach_screenshot(page, "Customer Details Filled")

            allure.attach(customer_name, "Customer Name", allure.attachment_type.TEXT)
            allure.attach(address, "Address", allure.attachment_type.TEXT)
            allure.attach(postal_code, "Postal Code", allure.attachment_type.TEXT)

        with allure.step("Save customer"):

            assert retry_action(click_if_exists, attempts=3, delay=1, page=page,
                                selector="#btnCustomerSubmit", timeout=5000), \
                "Save button not found: #btnCustomerSubmit"

            _log("Clicked Save & Close")
            safe_wait(page, 5000)
            attach_screenshot(page, "Customer Saved")

        with allure.step("Attach execution log"):
            attach_text_file(LOG_PATH, "Execution Log")

    except Exception as e:
        _log(f"Unhandled error during customer create script: {e}")
        attach_screenshot(page, "Failure Screenshot")
        attach_text_file(LOG_PATH, "Execution Log On Failure")
        allure.attach(str(e), "Exception", allure.attachment_type.TEXT)
        pytest.fail(f"Test failed due to exception: {e}")