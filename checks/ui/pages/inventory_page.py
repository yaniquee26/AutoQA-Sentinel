from playwright.sync_api import Page


class InventoryPage:
    def __init__(self, page: Page):
        self.page = page
        self.title = page.locator('[data-test="title"]')
        self.items = page.locator('[data-test="inventory-item"]')
        self.cart_badge = page.locator('[data-test="shopping-cart-badge"]')

    def add_first_product_to_cart(self):
        self.items.first.locator("button").click()