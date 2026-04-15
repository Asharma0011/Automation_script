from playwright.sync_api import sync_playwright
import random
import string
import time
from pathlib import Path

LOG_PATH = Path(__file__).parent / "employees_create.log"
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
    try:
        page.screenshot(path=str(path), full_page=True)
        _log(f"Screenshot saved: {path}")
    except Exception as e:
        _log(f"Screenshot failed: {e}")


def safe_wait(page, ms: int):
    try:
        page.wait_for_timeout(ms)
    except Exception:
        pass


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
        loc.fill("")
        loc.fill(text)
        _log(f"Filled {selector} with {text}")
        return True
    except Exception as e:
        _log(f"fill_if_exists failed for {selector}: {e}")
    return False


def type_if_exists(page, selector: str, text: str, timeout: int = 3000, delay_ms: int = 80):
    try:
        page.wait_for_selector(selector, timeout=timeout, state="visible")
        loc = page.locator(selector).first
        loc.click()
        safe_wait(page, 200)
        loc.press("Control+A")
        loc.press("Backspace")
        loc.type(text, delay=delay_ms)
        _log(f"Typed into {selector}: {text}")
        return True
    except Exception as e:
        _log(f"type_if_exists failed for {selector}: {e}")
        return False


def select_dropdown_by_text(page, selector, text, timeout=5000):
    try:
        page.wait_for_selector(selector, timeout=timeout, state="visible")
        page.locator(selector).first.select_option(label=text)
        _log(f"Selected '{text}' from {selector}")
        return True
    except Exception as e:
        _log(f"select_dropdown_by_text failed for {selector}: {e}")
        return False


def select_dropdown_first_valid_option(page, selector, label, timeout=5000):
    try:
        page.wait_for_selector(selector, timeout=timeout, state="visible")
        dropdown = page.locator(selector).first
        options = dropdown.locator("option")
        count = options.count()

        for i in range(count):
            txt = options.nth(i).inner_text().strip().lower()
            val = options.nth(i).get_attribute("value")
            if txt and txt not in ["select", "please select", "--select--"] and val not in [None, "", "0", "-1"]:
                dropdown.select_option(index=i)
                _log(f"{label} selected using {selector}: {txt}")
                return True

        _log(f"No valid option found for {label} using {selector}")
        return False
    except Exception as e:
        _log(f"select_dropdown_first_valid_option failed for {label} / {selector}: {e}")
        return False


def select2_choose_real_option(page, container_selector, label, max_wait_ms=12000):
    try:
        page.wait_for_selector(container_selector, timeout=5000, state="visible")
        page.locator(container_selector).first.click()
        _log(f"Clicked Select2 container for {label}: {container_selector}")

        deadline = time.time() + (max_wait_ms / 1000.0)

        while time.time() < deadline:
            option_selectors = [
                "li.select2-results__option",
                ".select2-results__option",
                ".select2-results li",
            ]

            for sel in option_selectors:
                try:
                    opts = page.locator(sel)
                    count = opts.count()
                    if count == 0:
                        continue

                    for i in range(count):
                        txt = (opts.nth(i).inner_text() or "").strip()
                        disabled = opts.nth(i).get_attribute("aria-disabled")
                        classes = (opts.nth(i).get_attribute("class") or "").lower()

                        invalid_values = [
                            "",
                            "select",
                            "searching...",
                            "loading more results...",
                            "no results found",
                        ]

                        if txt.lower() in invalid_values:
                            continue
                        if disabled == "true":
                            continue
                        if "loading-results" in classes:
                            continue

                        opts.nth(i).click()
                        _log(f"{label} selected: {txt}")
                        return True
                except Exception as e:
                    _log(f"{label} scan failed for {sel}: {e}")

            safe_wait(page, 700)

        page.keyboard.press("ArrowDown")
        safe_wait(page, 300)
        page.keyboard.press("Enter")
        _log(f"{label} selected by keyboard fallback")
        return True

    except Exception as e:
        _log(f"select2_choose_real_option failed for {label}: {e}")
        return False


def fill_postal_code(page, postal_code):
    selectors = [
        "#txtPostalCode",
        "#txtEmployeePostalCode",
        "#txtZipCode",
        "input[name*='Postal']",
        "input[name*='Zip']",
        "input[placeholder*='Postal']",
        "input[placeholder*='Zip']",
    ]

    for sel in selectors:
        if fill_if_exists(page, sel, postal_code, timeout=3000):
            return True

    try:
        label_block = page.locator("text=Postal/ Zip Code").first.locator("xpath=ancestor::div[1]")
        inp = label_block.locator("input").first
        inp.click()
        safe_wait(page, 200)
        inp.fill("")
        inp.type(postal_code, delay=70)
        _log(f"Postal code filled by label block: {postal_code}")
        return True
    except Exception as e:
        _log(f"Postal label block fill failed: {e}")

    return False


def fill_address_autocomplete(page, selector, search_text):
    try:
        page.wait_for_selector(selector, timeout=5000, state="visible")
        addr = page.locator(selector).first
        addr.click()
        safe_wait(page, 200)
        addr.press("Control+A")
        addr.press("Backspace")
        addr.type(search_text, delay=90)
        _log(f"Typed address search text: {search_text}")

        safe_wait(page, 2000)

        suggestion_selectors = [
            ".pac-item",
            ".ui-menu-item",
            ".autocomplete-suggestion",
            ".tt-suggestion",
            "li[role='option']",
            ".dropdown-menu li",
        ]

        deadline = time.time() + 10
        while time.time() < deadline:
            for sel in suggestion_selectors:
                try:
                    items = page.locator(sel)
                    count = items.count()
                    if count == 0:
                        continue

                    for i in range(count):
                        txt = (items.nth(i).inner_text() or "").strip()
                        if txt:
                            items.nth(i).click()
                            _log(f"Address selected from suggestions: {txt}")
                            safe_wait(page, 1500)
                            return True
                except Exception as e:
                    _log(f"Address suggestion scan failed for {sel}: {e}")

            safe_wait(page, 500)

        addr.click()
        safe_wait(page, 300)
        page.keyboard.press("ArrowDown")
        safe_wait(page, 400)
        page.keyboard.press("Enter")
        _log("Address selected by keyboard fallback")
        safe_wait(page, 1500)
        return True

    except Exception as e:
        _log(f"fill_address_autocomplete failed: {e}")
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
        page = browser.new_page(viewport={"width": 1440, "height": 900})

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

        # OPEN EMPLOYEES
        employee_menu_selectors = [
            "#MNU00005 a:has-text('Employees')",
            "a[href*='Employee']",
            "a[href*='Employees']",
            "a[href*='EmployeeList']",
            "a:has-text('Employees')",
            "text=Employees",
        ]

        opened_employees = False
        for sel in employee_menu_selectors:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=GLOBAL_TIMEOUT):
                _log(f"Opened Employees using {sel}")
                opened_employees = True
                break

        if not opened_employees:
            raise Exception("Employees menu not found")

        safe_wait(page, 3000)

        # CLICK NEW
        new_button_selectors = [
            "#btnAddEmployee",
            "#btnEmployeeAdd",
            "button:has-text('New')",
            "button:has-text('Add Employee')",
            "button:has-text('Create Employee')",
            "text=New",
        ]

        clicked_new = False
        for sel in new_button_selectors:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=5000):
                _log(f"Clicked New using {sel}")
                clicked_new = True
                break

        if not clicked_new:
            raise Exception("New Employee button not found")

        safe_wait(page, 2500)

        # WAIT FOR CREATE EMPLOYEE MODAL
        modal_ready = False
        modal_selectors = [
            "text=Create Employee",
            "#ddlEmployeeTitle",
            "#ddlCountry",
            "#ddlEmployeeState",
            "#select2-ddlEmployeeCities-container",
        ]

        for sel in modal_selectors:
            try:
                page.wait_for_selector(sel, timeout=8000, state="visible")
                _log(f"Employee modal detected with selector: {sel}")
                modal_ready = True
                break
            except Exception as e:
                _log(f"Modal wait failed for {sel}: {e}")

        if not modal_ready:
            _screenshot(page, "employee_modal_not_found.png")
            raise Exception("Employee create modal did not open")

        # TEST DATA
        first_name = "AUTO" + random_alpha(5)
        last_name = "EMP" + random_alpha(5)
        email = f"{first_name.lower()}.{last_name.lower()}@testmail.com"
        mobile = "9850088941"
        address_search = "Toronto"
        postal_code = "M5V2T6"

        # FIRST NAME
        first_name_selectors = [
            "#txtEmployeeFirstName",
            "input[name*='FirstName']",
            "input[id*='FirstName']",
        ]

        first_name_filled = False
        for sel in first_name_selectors:
            if retry_action(fill_if_exists, attempts=2, delay=1, page=page, selector=sel, text=first_name, timeout=5000):
                first_name_filled = True
                break

        if not first_name_filled:
            _screenshot(page, "first_name_not_filled.png")
            raise Exception("First Name field not found")

        safe_wait(page, 300)

        # LAST NAME
        last_name_selectors = [
            "#txtEmployeeLastName",
            "input[name*='LastName']",
            "input[id*='LastName']",
        ]

        last_name_filled = False
        for sel in last_name_selectors:
            if retry_action(fill_if_exists, attempts=2, delay=1, page=page, selector=sel, text=last_name, timeout=5000):
                last_name_filled = True
                break

        if not last_name_filled:
            _log("Last Name field not found with standard selectors")

        safe_wait(page, 300)

        # TITLE
        retry_action(
            select_dropdown_by_text,
            attempts=3,
            delay=1,
            page=page,
            selector="#ddlEmployeeTitle",
            text="Mr.",
            timeout=5000
        )

        safe_wait(page, 500)

        # EMAIL
        email_selectors = [
            "#txtEmail",
            "#txtEmployeeEmail",
            "input[name*='Email']",
            "input[placeholder*='abc@abc.com']",
        ]

        for sel in email_selectors:
            if retry_action(fill_if_exists, attempts=2, delay=1, page=page, selector=sel, text=email, timeout=5000):
                break

        safe_wait(page, 500)

        # ADDRESS AUTOCOMPLETE
        address_ok = retry_action(
            fill_address_autocomplete,
            attempts=3,
            delay=2,
            page=page,
            selector="input[placeholder*='Search By Address']",
            search_text=address_search
        )

        if not address_ok:
            _screenshot(page, "address_autocomplete_failed.png")
            raise Exception("Address autocomplete selection failed")

        safe_wait(page, 500)

        # COUNTRY
        country_selectors = [
            "#ddlCountry",
            "#ddlEmployeeCountry",
            "select[name*='Country']",
        ]

        for sel in country_selectors:
            if retry_action(select_dropdown_by_text, attempts=2, delay=1, page=page, selector=sel, text="Canada", timeout=5000):
                break

        safe_wait(page, 1200)

        # STATE / PROVINCE
        state_selectors = [
            "#ddlEmployeeState",
            "#ddlState",
            "#ddlProvince",
            "select[name*='State']",
            "select[name*='Province']",
        ]

        state_done = False
        for sel in state_selectors:
            if retry_action(select_dropdown_by_text, attempts=2, delay=1, page=page, selector=sel, text="Ontario", timeout=5000):
                state_done = True
                break
            if retry_action(select_dropdown_first_valid_option, attempts=2, delay=1, page=page, selector=sel, label="State/Province", timeout=5000):
                state_done = True
                break

        if not state_done:
            _log("State/Province dropdown not filled, proceeding")

        safe_wait(page, 3500)

        # CITY
        city_ok = retry_action(
            select2_choose_real_option,
            attempts=4,
            delay=2,
            page=page,
            container_selector="#select2-ddlEmployeeCities-container",
            label="City",
            max_wait_ms=12000
        )

        if not city_ok:
            _screenshot(page, "city_selection_failed.png")
            raise Exception("City dropdown not filled")

        safe_wait(page, 1000)

        # POSTAL CODE
        postal_ok = retry_action(
            fill_postal_code,
            attempts=3,
            delay=1,
            page=page,
            postal_code=postal_code
        )

        if not postal_ok:
            _screenshot(page, "postal_code_failed.png")
            raise Exception("Postal code not filled")

        safe_wait(page, 500)

        # MOBILE
        mobile_selectors = [
            "#txtMobile",
            "#txtEmployeeMobile",
            "input[name*='Mobile']",
        ]

        for sel in mobile_selectors:
            if retry_action(fill_if_exists, attempts=2, delay=1, page=page, selector=sel, text=mobile, timeout=5000):
                break

        safe_wait(page, 500)

        # DESIGNATION
        retry_action(
            select2_choose_real_option,
            attempts=3,
            delay=1,
            page=page,
            container_selector="#select2-ddlEmployeedesignation-container",
            label="Designation",
            max_wait_ms=8000
        )

        safe_wait(page, 700)

        # DEPARTMENT
        retry_action(
            select2_choose_real_option,
            attempts=3,
            delay=1,
            page=page,
            container_selector="#select2-ddlEmployeedepartment-container",
            label="Department",
            max_wait_ms=8000
        )

        safe_wait(page, 1200)

        # SAVE
        save_selectors = [
            "#btnEmployeeSubmit",
            "#btnEmployeeSave",
            "button:has-text('Save')",
            "text=Save",
        ]

        saved = False
        for sel in save_selectors:
            if retry_action(click_if_exists, attempts=3, delay=1, page=page, selector=sel, timeout=5000):
                _log(f"Clicked save using {sel}")
                saved = True
                break

        if not saved:
            raise Exception("Employee save button not found")

        safe_wait(page, 5000)

        _screenshot(page, "employee_created.png")
        _log("Employee creation attempted")
        print("Employee creation attempted")

    except Exception as e:
        _log(f"Unhandled error during employee create script: {e}")
        print("Unhandled error during employee create script:", e)
        try:
            if "page" in locals():
                _screenshot(page, "employee_create_error.png")
                html_path = Path(__file__).parent / "employee_create_error.html"
                html_path.write_text(page.content(), encoding="utf-8")
        except Exception:
            pass
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass