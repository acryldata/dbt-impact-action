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
    # Safely extract URN first (required field, but be defensive)
    urn = downstream.get("urn", "")

    # Safely extract platform name with fallback for entity types
    # that don't have platform in the GraphQL response (e.g., DataJob, DataFlow)
    platform_info = downstream.get("platform")
    if platform_info:
        platform = platform_info.get("name", "Unknown")
        display_name = (platform_info.get("properties") or {}).get("displayName")
        if display_name:
            platform = display_name
    else:
        # Fallback: try to extract platform from URN
        platform = _extract_platform_from_urn(urn)

    # Safely extract entity name
    properties = downstream.get("properties")
    if properties and properties.get("name"):
        name = properties["name"]
    else:
        name = urn if urn else "Unknown"

    url = datahub_url_from_urn(frontend_base_url, urn) if urn else ""

    entity_type: str = downstream.get("type", "Entity").capitalize()
    if downstream.get("subTypes"):
        type_names = downstream["subTypes"].get("typeNames")
        if type_names:
            entity_type = type_names[0]

    return f"{platform} {entity_type} [{name}]({url})"


def _extract_platform_from_urn(urn: str) -> str:
    """Extract platform name from URN as a fallback."""
    # URN format: urn:li:dataJob:(urn:li:dataFlow:(airflow,dag_id,PROD),task_id)
    # or: urn:li:dataset:(urn:li:dataPlatform:bigquery,project.dataset.table,PROD)
    # or: urn:li:dataFlow:(airflow,dag_id,PROD)
    try:
        if "dataPlatform:" in urn:
            # Extract from dataPlatform URN
            start = urn.find("dataPlatform:") + len("dataPlatform:")
            end = urn.find(",", start)
            if end > start:
                return urn[start:end].capitalize()
        elif "dataFlow:(" in urn:
            # Extract orchestrator from dataFlow URN
            # Format: urn:li:dataFlow:(orchestrator,flow_id,env)
            # or nested: urn:li:dataJob:(urn:li:dataFlow:(orchestrator,flow_id,env),task_id)
            start = urn.find("dataFlow:(") + len("dataFlow:(")
            end = urn.find(",", start)
            if end > start:
                return urn[start:end].capitalize()
    except Exception:
        pass
    return "Unknown"
