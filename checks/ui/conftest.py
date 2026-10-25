import pytest

from checks.ui.pages.inventory_page import InventoryPage
from checks.ui.pages.login_page import LoginPage

PASSWORD = "secret_sauce"


@pytest.fixture(autouse=True)
def short_timeouts(page):
    page.set_default_timeout(10_000)


@pytest.fixture
def inventory(page):
    login = LoginPage(page)
    login.open()
    login.login("standard_user", PASSWORD)
    return InventoryPage(page)