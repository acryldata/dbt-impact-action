import re

import pytest

from rendering import datahub_url_from_urn, format_entity, _extract_platform_from_urn

# Regex pattern to validate markdown link format: "Platform Type [name](url)"
MARKDOWN_LINK_PATTERN = re.compile(r"^[\w\s]+ [\w\s]+ \[.+\]\(https?://.+\)$")


def test_url_generation():
    assert (
        datahub_url_from_urn(
            "https://customer.acryl.io",
            "urn:li:dataset:(urn:li:dataPlatform:snowflake,snowflake_sample_data.tpch_sf1000.orders,PROD)",
        )
        == "https://customer.acryl.io/dataset/urn%3Ali%3Adataset%3A%28urn%3Ali%3AdataPlatform%3Asnowflake%2Csnowflake_sample_data.tpch_sf1000.orders%2CPROD%29"
    )


def test_format_entity_with_platform():
    """Test format_entity with a normal entity that has platform info."""
    entity = {
        "urn": "urn:li:dataset:(urn:li:dataPlatform:bigquery,project.dataset.table,PROD)",
        "type": "DATASET",
        "properties": {"name": "my_table"},
        "platform": {
            "name": "bigquery",
            "properties": {"displayName": "BigQuery"},
        },
        "subTypes": {"typeNames": ["Table"]},
    }
    result = format_entity("https://datahub.example.com", entity)

    # Validate exact format: "Platform Type [name](url)"
    assert (
        result
        == "BigQuery Table [my_table](https://datahub.example.com/dataset/urn%3Ali%3Adataset%3A%28urn%3Ali%3AdataPlatform%3Abigquery%2Cproject.dataset.table%2CPROD%29)"
    )
    assert MARKDOWN_LINK_PATTERN.match(result)


def test_format_entity_without_platform_display_name():
    """Test format_entity when platform has no displayName."""
    entity = {
        "urn": "urn:li:dataset:(urn:li:dataPlatform:snowflake,db.schema.table,PROD)",
        "type": "DATASET",
        "properties": {"name": "snowflake_table"},
        "platform": {"name": "snowflake"},
    }
    result = format_entity("https://datahub.example.com", entity)
    assert "snowflake" in result
    assert "snowflake_table" in result


def test_format_entity_missing_platform():
    """Test format_entity when platform key is missing (e.g., DataJob)."""
    entity = {
        "urn": "urn:li:dataJob:(urn:li:dataFlow:(airflow,dag_id,PROD),task_id)",
        "type": "DATA_JOB",
        "properties": {"name": "my_airflow_task"},
    }
    result = format_entity("https://datahub.example.com", entity)
    assert "Airflow" in result
    assert "my_airflow_task" in result


def test_format_entity_platform_is_none():
    """Test format_entity when platform is explicitly None."""
    entity = {
        "urn": "urn:li:dataset:(urn:li:dataPlatform:unknown,some.dataset,PROD)",
        "type": "DATASET",
        "properties": {"name": "some_dataset"},
        "platform": None,
    }
    result = format_entity("https://datahub.example.com", entity)
    assert "some_dataset" in result


def test_format_entity_missing_properties():
    """Test format_entity when properties key is missing."""
    entity = {
        "urn": "urn:li:dataset:(urn:li:dataPlatform:bigquery,project.dataset.table,PROD)",
        "type": "DATASET",
        "platform": {"name": "bigquery"},
    }
    result = format_entity("https://datahub.example.com", entity)
    assert "bigquery" in result
    assert "urn:li:dataset" in result


def test_format_entity_missing_properties_name():
    """Test format_entity when properties exists but name is missing."""
    entity = {
        "urn": "urn:li:dataset:(urn:li:dataPlatform:bigquery,project.dataset.table,PROD)",
        "type": "DATASET",
        "platform": {"name": "bigquery"},
        "properties": {},
    }
    result = format_entity("https://datahub.example.com", entity)
    assert "bigquery" in result


def test_format_entity_dataflow():
    """Test format_entity with DataFlow entity."""
    entity = {
        "urn": "urn:li:dataFlow:(airflow,my_dag,PROD)",
        "type": "DATA_FLOW",
        "properties": {"name": "my_dag"},
    }
    result = format_entity("https://datahub.example.com", entity)
    assert "Airflow" in result
    assert "my_dag" in result


def test_format_entity_with_subtypes():
    """Test format_entity uses subTypes when available."""
    entity = {
        "urn": "urn:li:dataset:(urn:li:dataPlatform:dbt,project.model,PROD)",
        "type": "DATASET",
        "properties": {"name": "my_model"},
        "platform": {"name": "dbt"},
        "subTypes": {"typeNames": ["Model"]},
    }
    result = format_entity("https://datahub.example.com", entity)
    assert "Model" in result
    assert "dbt" in result


def test_format_entity_without_subtypes():
    """Test format_entity falls back to type when subTypes is missing."""
    entity = {
        "urn": "urn:li:dashboard:(looker,123)",
        "type": "DASHBOARD",
        "properties": {"name": "Sales Dashboard"},
        "platform": {"name": "looker"},
    }
    result = format_entity("https://datahub.example.com", entity)
    assert "Dashboard" in result
    assert "Sales Dashboard" in result


def test_extract_platform_from_dataset_urn():
    """Test extracting platform from dataset URN."""
    urn = "urn:li:dataset:(urn:li:dataPlatform:bigquery,project.dataset.table,PROD)"
    assert _extract_platform_from_urn(urn) == "Bigquery"


def test_extract_platform_from_snowflake_urn():
    """Test extracting platform from snowflake dataset URN."""
    urn = "urn:li:dataset:(urn:li:dataPlatform:snowflake,db.schema.table,PROD)"
    assert _extract_platform_from_urn(urn) == "Snowflake"


def test_extract_platform_from_airflow_datajob_urn():
    """Test extracting platform from Airflow dataJob URN."""
    urn = "urn:li:dataJob:(urn:li:dataFlow:(airflow,dag_id,PROD),task_id)"
    assert _extract_platform_from_urn(urn) == "Airflow"


def test_extract_platform_from_airflow_dataflow_urn():
    """Test extracting platform from Airflow dataFlow URN."""
    urn = "urn:li:dataFlow:(airflow,my_dag,PROD)"
    assert _extract_platform_from_urn(urn) == "Airflow"


def test_extract_platform_from_dagster_urn():
    """Test extracting platform from Dagster URN."""
    urn = "urn:li:dataJob:(urn:li:dataFlow:(dagster,pipeline,PROD),task)"
    assert _extract_platform_from_urn(urn) == "Dagster"


def test_extract_platform_from_dagster_with_airflow_in_name():
    """Test that orchestrator is extracted from correct position, not from DAG name.

    Regression test: A Dagster pipeline named 'airflow_migration_pipeline' should
    return 'Dagster', not 'Airflow'.
    """
    urn = "urn:li:dataFlow:(dagster,airflow_migration_pipeline,PROD)"
    assert _extract_platform_from_urn(urn) == "Dagster"


def test_extract_platform_from_prefect_urn():
    """Test extracting platform from Prefect URN."""
    urn = "urn:li:dataFlow:(prefect,my_flow,PROD)"
    assert _extract_platform_from_urn(urn) == "Prefect"


def test_extract_platform_from_unknown_urn():
    """Test extracting platform from unknown URN format."""
    urn = "urn:li:unknown:something"
    assert _extract_platform_from_urn(urn) == "Unknown"


def test_extract_platform_from_empty_urn():
    """Test extracting platform from empty URN."""
    assert _extract_platform_from_urn("") == "Unknown"


def test_url_generation_with_suffix():
    """Test URL generation with suffix."""
    assert (
        datahub_url_from_urn(
            "https://customer.acryl.io",
            "urn:li:dataset:(urn:li:dataPlatform:snowflake,db.table,PROD)",
            suffix="Lineage",
        )
        == "https://customer.acryl.io/dataset/urn%3Ali%3Adataset%3A%28urn%3Ali%3AdataPlatform%3Asnowflake%2Cdb.table%2CPROD%29/Lineage"
    )


# Edge case tests


def test_format_entity_missing_urn_raises_error():
    """Test that format_entity raises KeyError when URN is missing.

    URN is the primary key in DataHub - if it's missing, that's a critical
    API bug that should fail loudly, not silently.
    """
    entity = {
        "type": "DATASET",
        "properties": {"name": "my_table"},
        "platform": {"name": "bigquery"},
    }
    with pytest.raises(KeyError, match="Required field 'urn' is missing"):
        format_entity("https://datahub.example.com", entity)


def test_format_entity_empty_downstream_raises_error():
    """Test that format_entity raises KeyError for empty downstream dict."""
    with pytest.raises(KeyError, match="Required field 'urn' is missing"):
        format_entity("https://datahub.example.com", {})


def test_extract_platform_from_invalid_urn():
    """Test extracting platform from a completely invalid URN."""
    assert _extract_platform_from_urn("not-a-valid-urn") == "Unknown"
    assert _extract_platform_from_urn("urn:li:") == "Unknown"
    assert _extract_platform_from_urn("random garbage") == "Unknown"


def test_extract_platform_from_malformed_dataflow_urn():
    """Test extracting platform from malformed dataFlow URN without parenthesis."""
    # This URN has dataFlow: but no opening parenthesis
    urn = "urn:li:dataFlow:malformed"
    assert _extract_platform_from_urn(urn) == "Unknown"
