import os


def test_bot_token_is_not_visible_to_checks():
    assert "BOT_TOKEN" not in os.environ