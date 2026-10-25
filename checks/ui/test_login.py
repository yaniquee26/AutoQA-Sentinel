import re

import pytest
from playwright.sync_api import expect

from checks.ui.pages.inventory_page import InventoryPage
from checks.ui.pages.login_page import LoginPage

PASSWORD = "secret_sauce"


def test_valid_user_can_log_in(page):
    login = LoginPage(page)
    login.open()
    login.login("standard_user", PASSWORD)

    expect(page).to_have_url(re.compile(r".*/inventory\.html"))
    expect(InventoryPage(page).title).to_have_text("Products")


@pytest.mark.parametrize(
    "username, password, expected_error",
    [
        ("standard_user", "wrong_password", "Username and password do not match"),
        ("", PASSWORD, "Username is required"),
        ("standard_user", "", "Password is required"),
        ("locked_out_user", PASSWORD, "this user has been locked out"),
    ],
    ids=["wrong_password", "empty_username", "empty_password", "locked_out_user"],
)
def test_invalid_login_shows_error(page, username, password, expected_error):
    login = LoginPage(page)
    login.open()
    login.login(username, password)

    expect(login.error).to_contain_text(expected_error)