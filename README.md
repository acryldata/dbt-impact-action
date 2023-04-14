# dbt-impact-analysis-action

This action will comment on your PRs with a summary of the impact of changes within a dbt project.

<p align="center" width="70%">
  <img src="impact-analysis-screenshot.png" alt="Impact Analysis Screenshot" width="600"/>
</p>

## Usage

```yml
name: Acryl Impact Analysis

on:
  pull_request:
    branches: [ "main" ]  # TODO(developer): Change this to your main branch.

permissions:
  contents: read
  pull-requests: write

jobs:
  impact-analysis:

    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3
      with:
        # We need the full git history to get a proper list of changed files.
        fetch-depth: 0

    # This piece is standard boilerplate for any dbt project.
    # It assumes that your requirements.txt file will install
    # dbt and the dbt adapter you're using.
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: "3.10"
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip wheel
        pip install -r requirements.txt

    - name: Run impact analysis
      uses: acryldata/dbt-impact-analysis-action@main
      with:
        # The name of your dbt adapter.
        # One of [bigquery, postgres, redshift, snowflake].
        # Let us know if you need support for another adapter.
        dbt_adapter: postgres

        # If your dbt project is not in the root of your repo,
        # specify the path to it here.
        # dbt_project_folder: .

        # Credentials to connect to Acryl.
        datahub_gms_host: https://<customer>.acryl.io/gms
        datahub_gms_token: ${{ secrets.ACRYL_GMS_TOKEN }}
        datahub_frontend_url: https://<customer>.acryl.io
```
