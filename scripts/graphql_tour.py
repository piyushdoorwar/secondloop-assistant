"""Appendix B: four small Admin GraphQL requests, raw.

python -m scripts.graphql_tour
"""

import json
import os

import httpx2 as httpx

from scripts.shopify_admin import API_VERSION, _token

URL = (
    f"https://{os.environ['SHOPIFY_SHOP']}"
    f"/admin/api/{API_VERSION}/graphql.json"
)


def post(query, variables=None):
    response = httpx.post(
        URL,
        json={"query": query, "variables": variables or {}},
        headers={"X-Shopify-Access-Token": _token()},
        timeout=30,
    )
    return response.status_code, response.json()


def show(title, result):
    status, body = result
    print(f"--- {title} (HTTP {status})")
    print(json.dumps(body, indent=2)[:1400])


# 1. Fields you name are the fields you get.
show("search by order name", post(
    """
    query FindOrder($q: String!) {
      orders(first: 1, query: $q) {
        nodes { id name displayFulfillmentStatus }
      }
    }
    """,
    {"q": "name:SL-1042"},
))

# 2. A field that does not exist fails the whole request.
show("unknown field", post(
    "query { shop { name nickname } }"
))

# 3. Connections page with cursors.
show("first page of two", post(
    """
    query Page($after: String) {
      orders(first: 2, after: $after, sortKey: CREATED_AT) {
        nodes { name }
        pageInfo { hasNextPage endCursor }
      }
    }
    """
))

# 4. Ask the schema about itself.
show("is returnReason deprecated?", post(
    """
    query {
      __type(name: "ReturnLineItemInput") {
        inputFields(includeDeprecated: true) {
          name isDeprecated deprecationReason
        }
      }
    }
    """
))
