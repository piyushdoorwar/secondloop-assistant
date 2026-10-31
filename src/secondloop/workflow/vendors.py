"""Real dispatch to Shopify and Slack for the worker."""

import httpx2 as httpx
from slack_sdk.errors import SlackApiError

from secondloop.cases import load_cases
from secondloop.shopify.client import ShopifyError
from secondloop.shopify.factory import admin_client
from secondloop.shopify.returns import (
    create_return,
    order_returns,
)
from secondloop import slack
from secondloop.workflow.worker import (
    Rejected,
    TryLater,
    Uncertain,
)

TRANSPORT = (httpx.TimeoutException, httpx.TransportError)


class Vendors:
    def __init__(self, slack_client=None):
        self.cases = load_cases()
        self.slack = slack_client

    def dispatch(self, op) -> str:
        if op["kind"] == "return":
            return self.send_return(op)
        return self.send_escalation(op)

    def send_return(self, op) -> str:
        case = self.cases[op["case_id"]]
        try:
            result = create_return(
                admin_client(case.shop), op["spec"]
            )
        except TRANSPORT as error:
            raise Uncertain(type(error).__name__)
        except ShopifyError as error:
            if error.code == "throttled":
                raise TryLater("throttled")
            raise Uncertain(error.code)
        if result["userErrors"]:
            raise Rejected(
                result["userErrors"][0]["message"]
            )
        created = result["return"]
        if not created or not created.get("id"):
            raise Uncertain("no_return_in_response")
        return created["name"]

    def send_escalation(self, op) -> str:
        spec = op["spec"]
        try:
            return slack.post(
                self.slack or slack.slack_client(),
                spec["channel"],
                spec["text"],
                op["id"],
            )
        except SlackApiError as error:
            raise Rejected(error.response["error"])
        except Exception as error:
            raise Uncertain(type(error).__name__)
