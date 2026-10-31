# secondloop-assistant

Companion code for **From APIs to MCP with Python** by Piyush Doorwar.

The book follows Mira, a backend engineer at SecondLoop (a fictional
online seller of refurbished electronics), as she connects Shopify, the
company's own operations service and Slack to a Claude assistant through
MCP, one level of authority at a time. This repository is that project.

Each chapter ends at a git tag (`ch02`, `ch03`, ...). Check one out to
see the code exactly as the chapter leaves it.

```bash
git clone https://github.com/piyushdoorwar/secondloop-assistant
cd secondloop-assistant
git checkout ch03
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

## Modes

The default test run needs no accounts and makes no paid calls.

| Setting | Effect |
| --- | --- |
| `SHOPIFY_MODE=fake` (default) | Shopify calls are answered by a contract fake that replays responses recorded from the book's development store (`data/shopify_recorded/`). |
| `SHOPIFY_MODE=live` | Calls go to your own Shopify development store. Set `SHOPIFY_SHOP`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`. |

Tests that call a real vendor or model are marked `live`:

```bash
python -m pytest -m live
```

Copy `.env.example` to `.env` for local settings. Never commit real
credentials.

## Recreate the lab store

The scenario data (three products, orders SL-1042 to SL-1046, shipments
and one open return) was created through the Admin API with test
payments. Against your own development store:

```bash
SHOPIFY_MODE=live python scripts/seed_products.py
SHOPIFY_MODE=live python scripts/seed_orders.py
SHOPIFY_MODE=live python scripts/seed_fulfillments.py
SHOPIFY_MODE=live python scripts/seed_return.py
SHOPIFY_MODE=live python scripts/record_shopify.py
```

The scripts write the IDs your store assigns to `scripts/*.json`; update
`data/cases.json` to point at your order IDs.

## Versions

Python 3.13+, MCP protocol revision 2026-07-28, FastMCP 4.1.4,
FastAPI 0.162.0, Anthropic Python SDK 2.3.0, Slack SDK 3.46.0,
Shopify Admin API 2026-10.

All people, customers and orders in the data are fictional.

## License

MIT. See [LICENSE](LICENSE).
