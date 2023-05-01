from rendering import datahub_url_from_urn


def test_url_generation():
    assert (
        datahub_url_from_urn(
            "https://customer.acryl.io",
            "urn:li:dataset:(urn:li:dataPlatform:snowflake,snowflake_sample_data.tpch_sf1000.orders,PROD)",
        )
        == "https://customer.acryl.io/dataset/urn%3Ali%3Adataset%3A%28urn%3Ali%3AdataPlatform%3Asnowflake%2Csnowflake_sample_data.tpch_sf1000.orders%2CPROD%29"
    )
