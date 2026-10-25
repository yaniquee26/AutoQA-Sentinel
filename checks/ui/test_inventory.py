from playwright.sync_api import expect


def test_inventory_shows_six_products(inventory):
    expect(inventory.items).to_have_count(6)


def test_add_to_cart_updates_badge(inventory):
    inventory.add_first_product_to_cart()

    expect(inventory.cart_badge).to_have_text("1")