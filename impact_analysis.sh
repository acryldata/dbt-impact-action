#!/bin/bash

set -euxo pipefail

# Check dbt installation.
cd "${DBT_PROJECT_FOLDER}"
dbt --version

# Install acryl-datahub package.
pip install acryl-datahub==0.10.1.2rc8
# pip cache remove 'acryl*'

# Set DBT_PROFILE_NAME if not provided.
if [ -z "${DBT_PROFILE_NAME}" ]; then
	echo 'Reading DBT_PROFILE_NAME from dbt_project.yml'
	DBT_PROFILE_NAME=$(python "${GITHUB_ACTION_PATH}/read_dbt_profile_name.py")
fi

# Print some debug info.
echo "dbt adapter: ${DBT_ADAPTER}"
echo "dbt profile name: ${DBT_PROFILE_NAME}"

# Replace the DBT_PROFILE_NAME for the wanted adapter with the actual profile name.
export DBT_PROFILES_DIR=${GITHUB_ACTION_PATH}/fake-dbt-profile
sed -i "s/DBT_PROFILE_NAME_${DBT_ADAPTER}/${DBT_PROFILE_NAME}/g" "${DBT_PROFILES_DIR}/profiles.yml"
cat "${DBT_PROFILES_DIR}/profiles.yml"

# Generate the previous manifest.
git checkout "${GITHUB_BASE_REF}"
dbt ls
cp -r target target-previous
git checkout -

# Run impact analysis script.
DBT_ARTIFACT_STATE_PATH=target-previous python "${GITHUB_ACTION_PATH}/impact_analysis.py"
cat impact_analysis.md

# Output a multiline string to an output parameter.
# Technique from https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#multiline-strings
EOF=$(dd if=/dev/urandom bs=15 count=1 status=none | base64)
{
	echo "IMPACT_ANALYSIS_MD<<$EOF"
	cat impact_analysis.md
	echo "$EOF"
} >> "$GITHUB_ENV"
