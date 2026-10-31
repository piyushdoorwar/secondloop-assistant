"""Store-level settings the policy check needs."""

SHOP_TIMEZONE = """
query ShopTimezone {
  shop { ianaTimezone }
}
"""


def read_timezone(client) -> str:
    data = client.query(SHOP_TIMEZONE, {})
    return data["shop"]["ianaTimezone"]
