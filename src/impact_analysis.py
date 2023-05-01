import json
import logging
import os
import pathlib
import subprocess
import traceback
from typing import Dict, List, Optional, TypedDict

from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
from datahub.metadata.schema_classes import DatasetPropertiesClass
from datahub.telemetry import telemetry

from rendering import datahub_url_from_urn, format_entity

OUTPUT_PATH = pathlib.Path("impact_analysis.md")
DBT_ID_PROP = "dbt_unique_id"
MAX_IMPACTED_DOWNSTREAMS = 30
MAX_DOWNSTREAMS_TO_FETCH = 1000


def get_graph() -> DataHubGraph:
    DATAHUB_SERVER = os.environ["DATAHUB_GMS_HOST"]
    DATAHUB_TOKEN: Optional[str] = os.getenv("DATAHUB_GMS_TOKEN")

    graph = DataHubGraph(
        DatahubClientConfig(server=DATAHUB_SERVER, token=DATAHUB_TOKEN)
    )

    return graph


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

    # dbt prints out a warning if nothing was found.
    if (
        "The selection criterion 'state:modified' does not match any nodes"
        in res.stdout
        and "No nodes selected!" in res.stdout
    ):
        return []

    try:
        dbt_nodes: List[DbtNodeInfo] = []
        for line in res.stdout.splitlines():
            dbt_info: DbtNodeInfo = json.loads(line)
            dbt_nodes.append(dbt_info)

        return dbt_nodes
    except json.decoder.JSONDecodeError as e:
        print(f"Unable to determine changed dbt models: {e}. Output was {res.stdout}")
        raise ImpactAnalysisError("Failed to parse dbt output") from e


def find_datahub_urns(graph: DataHubGraph, dbt_node_ids: List[str]) -> List[str]:
    if not dbt_node_ids:
        return []

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
    results: Dict = graph._post_generic(graph._search_endpoint, search_body)

    urns = [res["entity"] for res in results["value"]["entities"]]

    return urns


def get_datahub_info(graph: DataHubGraph, urn: str) -> Optional[DatasetPropertiesClass]:
    return graph.get_aspect(urn, DatasetPropertiesClass)


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


def get_impact_analysis(graph: DataHubGraph, urn: str):
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


@telemetry.with_telemetry()
def dbt_impact_analysis() -> str:
    graph = get_graph()
    DATAHUB_FRONTEND_URL = os.environ["DATAHUB_FRONTEND_URL"]

    # Step 1 - determine which dbt nodes are impacted by the changes in a given PR.
    changed_dbt_nodes = determine_changed_dbt_models()
    dbt_id_to_dbt_node = {node["unique_id"]: node for node in changed_dbt_nodes}
    # print(changed_dbt_nodes)

    # Step 2 - map dbt nodes to datahub urns.
    # In an ideal world, the datahub urns for dbt would just be the dbt node ids.
    urns = find_datahub_urns(graph, [node["unique_id"] for node in changed_dbt_nodes])
    datahub_node_props = {urn: get_datahub_info(graph, urn) for urn in urns}
    urn_to_dbt_id = {
        urn: node.customProperties[DBT_ID_PROP]
        for urn, node in datahub_node_props.items()
        if node
    }
    # print(urn_to_dbt_id)

    # Step 3 - generate downstream impact analysis for each datahub urn.
    downstreams_report = {urn: get_impact_analysis(graph, urn) for urn in urns}

    all_impacted_urns = {
        downstream["urn"]
        for downstreams in downstreams_report.values()
        for downstream in downstreams
    }

    # Step 4 - format the output message as markdown.
    output = "## Acryl Impact Analysis\n\n"
    output += f"- **{len(changed_dbt_nodes)}** dbt models changed\n"
    output += (
        f"- **{len(all_impacted_urns)}** downstream entities potentially impacted\n"
    )

    for urn, downstreams in downstreams_report.items():
        dbt_node = dbt_id_to_dbt_node[urn_to_dbt_id[urn]]

        output += f"\n### [{dbt_node['original_file_path']}]({datahub_url_from_urn(DATAHUB_FRONTEND_URL, urn)})\n\n"
        if downstreams:
            output += f"May impact **{len(downstreams)}** downstreams:\n"
            for downstream in downstreams[:MAX_IMPACTED_DOWNSTREAMS]:
                output += f"- {format_entity(DATAHUB_FRONTEND_URL, downstream)}\n"
            if len(downstreams) > MAX_IMPACTED_DOWNSTREAMS:
                output += f"- ...and [{len(downstreams) - MAX_IMPACTED_DOWNSTREAMS} more]({datahub_url_from_urn(DATAHUB_FRONTEND_URL, urn, suffix='/Lineage')})\n"
        else:
            output += "No downstreams impacted.\n"

    output += "\n\n_If a dbt model is reported as changed even though it's file contents have not changed, it's likely because a dbt macro or other metadata has changed._\n\n"

    return output


def main():
    try:
        output = dbt_impact_analysis()

        OUTPUT_PATH.write_text(output)
    except Exception as e:
        traceback.print_exc()
        print(f"ERROR: {e}")
        OUTPUT_PATH.write_text(
            f"""## Acryl Impact Analysis

Failed to run impact analysis: {e}

See the logs for full details.
"""
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("datahub").setLevel(logging.DEBUG)
    logging.getLogger(__name__).setLevel(logging.DEBUG)

    main()
