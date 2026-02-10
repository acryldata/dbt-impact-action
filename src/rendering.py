import logging
from typing import Optional

from datahub.utilities.urns.urn import Urn, guess_entity_type

logger = logging.getLogger(__name__)


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
    """Format a downstream entity as a markdown link for display.

    Args:
        frontend_base_url: The base URL of the DataHub frontend (e.g., "https://datahub.example.com")
        downstream: A dictionary containing entity data from the GraphQL response.
            Expected keys: urn (required), type, platform, properties, subTypes

    Returns:
        A markdown formatted string like "Platform EntityType [name](url)"
        Falls back gracefully if optional fields are missing.

    Raises:
        KeyError: If the required 'urn' field is missing from downstream.
    """
    # URN is required - fail fast if missing (it's the primary key in DataHub)
    if "urn" not in downstream:
        raise KeyError("Required field 'urn' is missing from downstream entity")
    urn = downstream["urn"]

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
        name = urn  # URN is guaranteed to exist at this point

    url = datahub_url_from_urn(frontend_base_url, urn)

    entity_type: str = downstream.get("type", "Entity").capitalize()
    if downstream.get("subTypes"):
        type_names = downstream["subTypes"].get("typeNames")
        if type_names:
            entity_type = type_names[0]

    return f"{platform} {entity_type} [{name}]({url})"


def _extract_platform_from_urn(urn: str) -> str:
    """Extract platform name from URN as a fallback when platform field is missing.

    Uses the DataHub URN utility library to properly parse URNs and extract
    platform/orchestrator information. Handles all entity types including:
    - Dataset URNs (extracts platform)
    - DataFlow URNs (extracts orchestrator)
    - DataJob URNs (extracts orchestrator from nested DataFlow URN)

    Args:
        urn: The URN string to parse.

    Returns:
        The capitalized platform/orchestrator name, or "Unknown" if parsing fails.
    """
    if not urn:
        return "Unknown"

    try:
        urn_obj = Urn.from_string(urn)

        # For DataJob URNs, get the nested DataFlow URN first
        if hasattr(urn_obj, "flow"):
            flow_urn = Urn.from_string(urn_obj.flow)
            if hasattr(flow_urn, "orchestrator"):
                return flow_urn.orchestrator.capitalize()

        # Try different attributes based on entity type
        # DatasetUrn has 'platform', DataFlowUrn has 'orchestrator'
        for attr in ["orchestrator", "platform", "dashboard_tool"]:
            try:
                value = getattr(urn_obj, attr, None)
                if value:
                    # If it's a platform URN, extract the platform name
                    if "dataPlatform:" in str(value):
                        platform_urn = Urn.from_string(str(value))
                        return platform_urn.entity_ids[0].capitalize()
                    return str(value).capitalize()
            except (AttributeError, IndexError):
                continue

        # No known platform attribute found - log for visibility
        entity_type = urn_obj.entity_type
        logger.warning(
            f"Could not extract platform from URN '{urn}' (entity_type={entity_type}). "
            f"Consider adding support for this entity type."
        )

    except Exception as e:
        logger.warning(f"Failed to extract platform from URN '{urn}': {e}")

    return "Unknown"
