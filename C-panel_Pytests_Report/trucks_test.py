import re
import time
from pathlib import Path
from playwright.sync_api import Page, expect
import pytest

# ensure repo root is on sys.path for imports of local packages
import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# try to import Allure functions conditionally
try:
    import allure
    _HAS_ALLURE = True
except Exception:
    _HAS_ALLURE = False

# import shared helpers
from Automation.helpers import click_if_exists, fill_if_exists, retry_action, retry_select, choose_first_select_option, safe_wait

# Add small helper utilities for robust interactions (copied/adapted patterns from Automation/Trucks.py)
GLOBAL_TIMEOUT = 20000
RETRY_ATTEMPTS = 5
RETRY_DELAY = 1


def _screenshot_on_failure(page: Page, path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=path, full_page=True)
    except Exception:
        pass
    # attach to allure if available
    if _HAS_ALLURE:
        try:
            allure.attach.file(path, name=Path(path).name, attachment_type=allure.attachment_type.PNG)
        except Exception:
            pass


@pytest.mark.parametrize("corp,user,password", [
    ("AFMDEMO", "Asharma", "Avaal@123"),
])
def test_create_truck_in_cpanel(page: Page, corp: str, user: str, password: str):
    """Login, open C-Panel -> Trucks, create a truck and verify the modal closes.

    Notes:
    - Attempts multiple locator fallbacks for resilience.
    - Tries several candidate selectors for Registration State/Province.
    """
    url = "https://afm2020.com/"

    page.goto(url)
    page.wait_for_load_state("networkidle")

    # Login
    page.locator("#txtCorporateId").fill(corp)
    page.locator("#txtUserName").fill(user)
    page.locator("#txtPassword").fill(password)

    # Click sign in with robust fallback
    clicked = False
    for sel in ["#signin", "button:has-text('Sign In')", "text=Sign In", "#btnSignIn"]:
        try:
            page.locator(sel).click(timeout=5000)
            clicked = True
            break
        except Exception:
            continue
    if not clicked:
        try:
            page.get_by_role("button", name=re.compile(r"sign\s*in", re.I)).click()
        except Exception:
            # final fallback: click first button
            page.locator("button").first.click()

    page.wait_for_load_state("networkidle")
    time.sleep(1)

    # Open C-Panel then Trucks
    cpanel_clicked = False
    for sel in ["a[data-id='#MNU00005']", "a:has-text('C-PANEL')", "a:has-text('C Panel')", "xpath=//*[@id=\'divMenuHTML\']/div[1]/ul/li[5]/a/span"]:
        try:
            page.locator(sel).click(timeout=8000)
            cpanel_clicked = True
            break
        except Exception:
            continue
    assert cpanel_clicked, "Could not open C-Panel menu"

    time.sleep(1)
    trucks_clicked = False
    for sel in ["#MNU00005 a:has-text('Trucks')", "a[href*='Masters/Truck/TruckList']", "a:has-text('Trucks')", "text=Trucks"]:
        try:
            page.locator(sel).click(timeout=8000)
            trucks_clicked = True
            break
        except Exception:
            continue
    assert trucks_clicked, "Could not open Trucks page"

    time.sleep(1)
    # Click Add Truck
    add_clicked = False
    for sel in ['#btnAddTruck', '#btnAddNewTruck', "button:has-text('Add Truck')", "text=Add Truck"]:
        try:
            page.locator(sel).click(timeout=8000)
            add_clicked = True
            break
        except Exception:
            continue

    assert add_clicked, "Could not open Add Truck modal"

    # Wait for modal (make this robust by retrying the click if the modal doesn't appear)
    def _modal_is_visible(p):
        try:
            loc = p.locator('#myTruckModal')
            if loc.count() == 0:
                return False
            # check style/display, class 'in', or bounding rect
            try:
                visible = p.eval_on_selector('#myTruckModal', "el => { const s = window.getComputedStyle(el); const rect = el.getBoundingClientRect(); return (s && s.display !== 'none' && rect.width>0 && rect.height>0) || el.classList.contains('in'); }")
                return bool(visible)
            except Exception:
                return False
        except Exception:
            return False

    modal_visible = False
    for attempt in range(6):
        try:
            # first wait for selector attached
            page.locator('#myTruckModal').wait_for(state='attached', timeout=3000)
        except Exception:
            # try clicking add again to trigger modal
            retry_action(click_if_exists, attempts=2, delay=1, page=page, selector='#btnAddTruck', timeout=3000)
        # now poll JS visibility
        if _modal_is_visible(page):
            modal_visible = True
            break
        time.sleep(1)

    if not modal_visible:
        # capture debug info and fail
        _screenshot_on_failure(page, 'ai/trucks_test_failure_modal_missing.png')
        try:
            page_html = page.content()
            Path('ai').joinpath('trucks_test_no_modal_page.html').write_text(page_html, encoding='utf-8')
            if _HAS_ALLURE:
                try:
                    allure.attach(page_html, name='trucks_test_no_modal_page.html', attachment_type=allure.attachment_type.HTML)
                except Exception:
                    pass
        except Exception:
            pass
        raise AssertionError('Add Truck modal did not appear after retries')

    # Fill required fields
    truck_no = 'AUTO' + ''.join(re.findall(r"\w", str(time.time())))[-4:]
    plate_no = 'PL' + ''.join(re.findall(r"\d", str(time.time())))[-4:]
    try:
        page.locator('#txtTruckNumber').fill(truck_no, timeout=8000)
        page.locator('#txtTruckPlateNumber').fill(plate_no, timeout=8000)
    except Exception:
        _screenshot_on_failure(page, 'ai/trucks_test_failure_fill.png')
        raise

    # Fill Registration State / Province robustly (try multiple select IDs and select2 fallbacks)
    try:
        state_selected = False
        # Try several select IDs that the app may use
        for sel in ['select#ddlTruckStates', 'select#ddlFleetStates', 'select#ddlTruckState', 'select#ddlFleetState']:
            try:
                v = choose_first_select_option(page, sel)
                if v:
                    state_selected = True
                    break
            except Exception:
                continue

        # If not selected, try select2 containers
        if not state_selected:
            if retry_action(click_if_exists, page=page, selector='#select2-ddlTruckStates-container'):
                # pick first result
                retry_action(click_if_exists, page=page, selector='.select2-results__option', attempts=3)
                state_selected = True
            elif retry_action(click_if_exists, page=page, selector='#select2-ddlFleetStates-container'):
                retry_action(click_if_exists, page=page, selector='.select2-results__option', attempts=3)
                state_selected = True

        if not state_selected:
            # give up gracefully but capture a screenshot
            _screenshot_on_failure(page, 'ai/trucks_test_warning_no_reg_selector.png')
    except Exception:
        _screenshot_on_failure(page, 'ai/trucks_test_warning_no_reg_selector.png')

    # Ensure Fleet is selected (choose first usable option)
    try:
        fleet_ok = choose_first_select_option(page, 'select#ddlTruckFleet')
        if not fleet_ok:
            # try alternative ids
            choose_first_select_option(page, 'select#ddlTruckFleets')
    except Exception:
        pass

    # Select Truck Type (Tractor (semi) has value '19' commonly) and Fuel Type
    if not retry_select(page, 'select#ddlTruckVehcileSubType', value='19'):
        retry_select(page, 'select#ddlTruckVehcileSubType', index=1)
    if not retry_select(page, 'select#ddlTruckFuelType', value='SpecialDiesel'):
        retry_select(page, 'select#ddlTruckFuelType', index=1)

    # Trigger change events by blurring
    try:
        page.locator('#txtTruckNumber').press('Tab')
    except Exception:
        pass

    # Submit
    clicked_submit = False
    submit_selectors = ['#btnTruckSubmit', '#btnSaveTruck', "button:has-text('Submit')", "button:has-text('Save')"]
    for sel in submit_selectors:
        try:
            page.locator(sel).click(timeout=8000)
            clicked_submit = True
            break
        except Exception:
            continue

    # Try additional submit buttons by id (common variants)
    if not clicked_submit:
        for sid in ['#btnTruckSubmitAndNext', '#btnTruckSubmitAndNew']:
            try:
                page.locator(sid).click(timeout=5000)
                clicked_submit = True
                break
            except Exception:
                continue

    # If basic selectors didn't work, try to click submit via JS inside the modal and capture debug info
    if not clicked_submit:
        # Capture screenshot and modal HTML for debugging
        before_path = 'ai/trucks_test_failure_before_submit.png'
        _screenshot_on_failure(page, before_path)
        try:
            modal_html = page.locator('#myTruckModal').inner_html()
            modal_path = Path('ai').joinpath('trucks_test_modal.html')
            modal_path.write_text(modal_html, encoding='utf-8')
            if _HAS_ALLURE:
                try:
                    allure.attach(modal_html, name='trucks_test_modal.html', attachment_type=allure.attachment_type.HTML)
                except Exception:
                    pass
        except Exception:
            try:
                # fallback: save full page HTML
                full_html = page.content()
                full_path = Path('ai').joinpath('trucks_test_fullpage.html')
                full_path.write_text(full_html, encoding='utf-8')
                if _HAS_ALLURE:
                    try:
                        allure.attach(full_html, name='trucks_test_fullpage.html', attachment_type=allure.attachment_type.HTML)
                    except Exception:
                        pass
            except Exception:
                pass

        # Try force-clicking the main submit buttons
        try:
            btn = page.locator('#btnTruckSubmit')
            btn.wait_for(state='visible', timeout=3000)
            btn.scroll_into_view_if_needed()
            btn.click(force=True)
            clicked_submit = True
        except Exception:
            try:
                btn2 = page.locator('#btnTruckSubmitAndNext')
                btn2.scroll_into_view_if_needed()
                btn2.click(force=True)
                clicked_submit = True
            except Exception:
                pass

    # Final JS-based fallbacks if still not clicked
    if not clicked_submit:
        try:
            page.eval_on_selector_all('#myTruckModal button', 'buttons => { if (buttons.length) { buttons[buttons.length-1].click(); return true;} return false }')
            clicked_submit = True
        except Exception:
            try:
                page.eval_on_selector('#myTruckModal form', 'f => { f.submit(); return true }')
                clicked_submit = True
            except Exception:
                clicked_submit = False

    assert clicked_submit, "Could not click submit for Truck"

    # Wait for response / modal close
    try:
        # Wait a bit longer to allow server processing and modal to close
        expect(page.locator('#myTruckModal')).not_to_be_visible(timeout=30000)
    except Exception:
        # If modal still visible, try alternative success checks: success alert or new row in table
        _screenshot_on_failure(page, 'ai/trucks_test_failure_after_submit.png')
        # try to detect success message
        try:
            if page.locator('.alert-success').is_visible():
                return
        except Exception:
            pass
        # try to find truck number in the Trucks table/list
        try:
            # Small delay to allow list refresh
            time.sleep(2)
            if page.locator(f"text={truck_no}").count() > 0:
                return
        except Exception:
            pass
        # nothing worked, raise
        raise

    # Optionally write the created truck number to a small log for reference
    try:
        Path('ai/created_trucks.txt').parent.mkdir(parents=True, exist_ok=True)
        with open('ai/created_trucks.txt', 'a', encoding='utf-8') as f:
            f.write(f"{truck_no},{plate_no}\n")
    except Exception:
        pass

