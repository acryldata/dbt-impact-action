import json
import os
import pathlib
import subprocess
from typing import Dict, List, Optional, TypedDict

from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
from datahub.metadata.schema_classes import DatasetPropertiesClass
from datahub.utilities.urns.urn import Urn, guess_entity_type
from datahub.telemetry import telemetry

DATAHUB_SERVER = os.environ["DATAHUB_GMS_HOST"]
DATAHUB_TOKEN: Optional[str] = os.getenv("DATAHUB_GMS_TOKEN")
DATAHUB_FRONTEND_URL = os.environ["DATAHUB_FRONTEND_URL"]

OUTPUT_PATH = pathlib.Path("impact_analysis.md")
DBT_ID_PROP = "dbt_unique_id"
MAX_IMPACTED_DOWNSTREAMS = 50
MAX_DOWNSTREAMS_TO_FETCH = 1000

graph = DataHubGraph(DatahubClientConfig(server=DATAHUB_SERVER, token=DATAHUB_TOKEN))


class ImpactAnalysisError(Exception):
    pass


class DbtNodeInfo(TypedDict):
    unique_id: str
    original_file_path: str


def determine_changed_dbt_models() -> List[DbtNodeInfo]:
    if "DBT_ARTIFACT_STATE_PATH" not in os.environ:
        raise ValueError("DBT_ARTIFACT_STATE_PATH environment variable must be set")

    # Running dbt ls also regenerates the manifest file, so it
    # will always produce output that is up-to-date with the latest changes.
    try:
        res = subprocess.run(
            [
                "dbt",
                "ls",
                # fmt: off
                # Use the manifest file from the previous run.
                "-s", "state:modified",
                # Limit to desired node types.
                "--resource-type", "model",
                "--resource-type", "snapshot",
                # Output formatting.
                "--output", "json",
                "--output-keys", "unique_id,original_file_path",
                # fmt: on
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise ImpactAnalysisError("Unable to determine changed dbt nodes") from e

    try:
        dbt_nodes: List[DbtNodeInfo] = []
        for line in res.stdout.splitlines():
            dbt_info: DbtNodeInfo = json.loads(line)
            dbt_nodes.append(dbt_info)

        return dbt_nodes
    except json.decoder.JSONDecodeError as e:
        print(f"Unable to determine changed dbt models: {e}. Output was {res.stdout}")
        raise ImpactAnalysisError("Failed to parse dbt output") from e


def find_datahub_urns(dbt_node_ids: List[str]) -> List[str]:
    filter_conditions = [
        {
            "field": "customProperties",
            "value": f"{DBT_ID_PROP}={dbt_node_id}",
            "condition": "EQUAL",
        }
        for dbt_node_id in dbt_node_ids
    ]

    search_body = {
        "input": "*",
        "entity": "dataset",
        "start": 0,
        "count": 10000,
        "filter": {"or": [{"and": [filter_cond]} for filter_cond in filter_conditions]},
    }
    results: Dict = graph._post_generic(graph._get_search_endpoint(), search_body)

    urns = [res["entity"] for res in results["value"]["entities"]]

    return urns


def get_datahub_info(urn: str):
    return graph.get_aspects_for_entity(
        urn,
        aspects=["datasetProperties"],
        aspect_types=[DatasetPropertiesClass],
    )


IMPACT_ANALYSIS_QUERY = """\
query GetLineage($urn: String!, $count: Int!) {
  searchAcrossLineage(
    input: {
      urn: $urn,
      direction: DOWNSTREAM,
      count: $count,
    }
  ) {
    searchResults {
      entity {
        urn
        type
        ... on Dataset {
          properties {
            name
          }
          platform {
            name
            properties {
              displayName
            }
          }
          subTypes {
            typeNames
          }
          siblings {
            isPrimary
          }
        }
        ... on Chart {
          properties {
            name
          }
          platform {
            name
            properties {
              displayName
            }
          }
        }
        ... on Dashboard {
          properties {
            name
          }
          platform {
            name
            properties {
              displayName
            }
          }
        }
      }
      degree
    }
  }
}
"""


def get_impact_analysis(urn: str):
    result = graph.execute_graphql(
        IMPACT_ANALYSIS_QUERY,
        variables={
            "urn": urn,
            "count": MAX_DOWNSTREAMS_TO_FETCH,
        },
    )

    downstreams = result["searchAcrossLineage"]["searchResults"]

    # Filter out the non-primary siblings.
    downstreams = [
        downstream
        for downstream in downstreams
        if (downstream["entity"].get("siblings") or {}).get("isPrimary") is not False
    ]

    # Sort by number of hops from the root node.
    # downstreams.sort(key=lambda x: x["degree"])

    downstream_details = [downstream["entity"] for downstream in downstreams]
    print(f"urn: {urn}, downstreams: {len(downstream_details)}")
    return downstream_details


def datahub_url_from_urn(urn: str, suffix: str = None) -> str:
    entity_type = guess_entity_type(urn)
    if entity_type == "dataJob":
        entity_type = "tasks"
    elif entity_type == "dataFlow":
        entity_type = "pipelines"

    url = f"{DATAHUB_FRONTEND_URL}/{entity_type}/{Urn.url_encode(urn)}"
    if suffix:
        url += f"/{suffix}"
    return url


def format_entity(downstream: Dict) -> str:
    platform = downstream["platform"]["name"]
    if downstream["platform"].get("properties", {}).get("displayName"):
        platform = downstream["platform"]["properties"]["displayName"]

    name = downstream["properties"]["name"]
    url = datahub_url_from_urn(downstream["urn"])

    type: str = downstream["type"].capitalize()
    if downstream.get("subTypes"):
        type = downstream["subTypes"]["typeNames"][0]

    return f"{platform} {type} [{name}]({url})"


@telemetry.with_telemetry()
def dbt_impact_analysis():
    # Step 1 - determine which dbt nodes are impacted by the changes in a given PR.
    changed_dbt_nodes = determine_changed_dbt_models()
    dbt_id_to_dbt_node = {node["unique_id"]: node for node in changed_dbt_nodes}
    # print(changed_dbt_nodes)

    # Step 2 - map dbt nodes to datahub urns.
    # In an ideal world, the datahub urns for dbt would just be the dbt node ids.
    urns = find_datahub_urns([node["unique_id"] for node in changed_dbt_nodes])
    datahub_nodes = {urn: get_datahub_info(urn) for urn in urns}
    urn_to_dbt_id = {
        urn: node["datasetProperties"].customProperties[DBT_ID_PROP]
        for urn, node in datahub_nodes.items()
    }
    # print(urn_to_dbt_id)

    # Step 3 - generate downstream impact analysis for each datahub urn.
    downstreams_report = {urn: get_impact_analysis(urn) for urn in urns}

    # Step 4 - format the output message as markdown.
    all_impacted_urns = {
        downstream["urn"]
        for downstreams in downstreams_report.values()
        for downstream in downstreams
    }

    output = "# Acryl Impact Analysis\n\n"
    output += f"- **{len(changed_dbt_nodes)}** dbt models changed\n"
    output += (
        f"- **{len(all_impacted_urns)}** downstream entities potentially impacted\n"
    )

    for urn, downstreams in downstreams_report.items():
        dbt_node = dbt_id_to_dbt_node[urn_to_dbt_id[urn]]

        output += (
            f"\n## [{dbt_node['original_file_path']}]({datahub_url_from_urn(urn)})\n\n"
        )
        if downstreams:
            output += f"May impact **{len(downstreams)}** downstreams:\n"
            for downstream in downstreams[:MAX_IMPACTED_DOWNSTREAMS]:
                output += f"- {format_entity(downstream)}\n"
            if len(downstreams) > MAX_IMPACTED_DOWNSTREAMS:
                output += f"- ...and [{len(downstreams) - MAX_IMPACTED_DOWNSTREAMS} more]({datahub_url_from_urn(urn, suffix='/Lineage')})\n"
        else:
            output += f"No downstreams impacted.\n"

    output += f"\n\n_If a dbt model is reported as changed even though it's file contents have not changed, it's likely because a dbt macro or other metadata has changed._\n\n"

    OUTPUT_PATH.write_text(output)


def main():
    try:
        dbt_impact_analysis()
    except Exception as e:
        print(f"ERROR: {e}")
        OUTPUT_PATH.write_text(
            f"""# Acryl Impact Analysis

Failed to run impact analysis: {e}

See the logs for full details.
"""
        )


if __name__ == "__main__":
    main()
