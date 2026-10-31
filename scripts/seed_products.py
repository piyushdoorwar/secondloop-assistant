import json, sys

sys.path.insert(0, "scripts")
from shopify_admin import gql

PRODUCTS = [
    ("Refurbished 14-inch Laptop", "LAP-14-R", "649.00"),
    ("USB-C Charger 65W", "CHG-65-C", "39.00"),
    (
        "Refurbished Wireless Headphones",
        "HDP-BT-R",
        "89.00",
    ),
]
M = """
mutation Seed($input: ProductSetInput!) {
  productSet(input: $input, synchronous: true) {
    product { id title variants(first: 1) { nodes { id sku } } }
    userErrors { field message code }
  }
}"""
out = {}
for title, sku, price in PRODUCTS:
    found = gql(
        "query($q:String!){productVariants(first:1, query:$q){nodes{id sku product{id}}}}",
        {"q": f"sku:{sku}"},
    )["productVariants"]["nodes"]
    if found:
        out[sku] = {
            "product_id": found[0]["product"]["id"],
            "variant_id": found[0]["id"],
        }
        continue
    d = gql(
        M,
        {
            "input": {
                "title": title,
                "status": "ACTIVE",
                "vendor": "SecondLoop",
                "productOptions": [
                    {
                        "name": "Title",
                        "values": [
                            {"name": "Default Title"}
                        ],
                    }
                ],
                "variants": [
                    {
                        "optionValues": [
                            {
                                "optionName": "Title",
                                "name": "Default Title",
                            }
                        ],
                        "sku": sku,
                        "price": price,
                    }
                ],
            }
        },
    )["productSet"]
    if d["userErrors"]:
        raise SystemExit(json.dumps(d["userErrors"]))
    v = d["product"]["variants"]["nodes"][0]
    out[sku] = {
        "product_id": d["product"]["id"],
        "variant_id": v["id"],
    }
print(json.dumps(out, indent=1))
json.dump(
    out, open("scripts/seed_products.json", "w"), indent=1
)
