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
        urn = downstream.get("urn", "")
        platform = _extract_platform_from_urn(urn)

    # Safely extract entity name
    properties = downstream.get("properties")
    if properties and properties.get("name"):
        name = properties["name"]
    else:
        name = downstream.get("urn", "Unknown")

    url = datahub_url_from_urn(frontend_base_url, downstream["urn"])

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
    try:
        if "dataPlatform:" in urn:
            # Extract from dataPlatform URN
            start = urn.find("dataPlatform:") + len("dataPlatform:")
            end = urn.find(",", start)
            if end > start:
                return urn[start:end].capitalize()
        elif "dataFlow:" in urn or "dataJob:" in urn:
            # Extract orchestrator from dataFlow/dataJob URN
            # Format: urn:li:dataJob:(urn:li:dataFlow:(orchestrator,...),...)
            for orchestrator in ["airflow", "dagster", "prefect", "argo", "spark"]:
                if orchestrator in urn.lower():
                    return orchestrator.capitalize()
    except Exception:
        pass
    return "Unknown"
