"""Post approved escalations to one Slack channel."""

import os

from slack_sdk import WebClient

EVENT_TYPE = "secondloop_operation"


def slack_client() -> WebClient:
    return WebClient(
        token=os.environ["SLACK_BOT_TOKEN"], timeout=10
    )


def operations_channel() -> str:
    return os.environ["SLACK_OPERATIONS_CHANNEL"]


def post(client, channel, text, operation_id) -> str:
    """Post once; return the message timestamp."""
    response = client.chat_postMessage(
        channel=channel,
        text=text,
        unfurl_links=False,
        unfurl_media=False,
        metadata={
            "event_type": EVENT_TYPE,
            "event_payload": {
                "operation_id": operation_id
            },
        },
    )
    return response["ts"]


def find_posted(client, channel, operation_id, since):
    """The ts of a message carrying this operation ID."""
    history = client.conversations_history(
        channel=channel,
        oldest=str(since),
        include_all_metadata=True,
        limit=200,
    )
    for message in history["messages"]:
        meta = message.get("metadata") or {}
        payload = meta.get("event_payload") or {}
        if payload.get("operation_id") == operation_id:
            return message["ts"]
    return None


def escape(text: str) -> str:
    """Stop text from becoming Slack markup."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
