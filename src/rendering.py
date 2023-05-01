from typing import Optional

from datahub.utilities.urns.urn import Urn, guess_entity_type


def datahub_url_from_urn(
    frontend_base_url: str, urn: str, suffix: Optional[str] = None
) -> str:
    entity_type = guess_entity_type(urn)
    if entity_type == "dataJob":
        entity_type = "tasks"
    elif entity_type == "dataFlow":
        entity_type = "pipelines"

    url = f"{frontend_base_url}/{entity_type}/{Urn.url_encode(urn)}"
    if suffix:
        url += f"/{suffix}"
    return url


def format_entity(frontend_base_url: str, downstream: dict) -> str:
    platform = downstream["platform"]["name"]
    if downstream["platform"].get("properties", {}).get("displayName"):
        platform = downstream["platform"]["properties"]["displayName"]

    name = downstream["properties"]["name"]
    url = datahub_url_from_urn(frontend_base_url, downstream["urn"])

    type: str = downstream["type"].capitalize()
    if downstream.get("subTypes"):
        type = downstream["subTypes"]["typeNames"][0]

    return f"{platform} {type} [{name}]({url})"
