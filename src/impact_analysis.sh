#!/bin/bash

set -euxo pipefail

# Check dbt installation.
cd "${DBT_PROJECT_FOLDER}"
dbt --version

# Install dbt deps.
dbt deps

# Install our requirements.
pip install -r "${GITHUB_ACTION_PATH}/requirements.txt"

# Set DBT_PROFILE_NAME if not provided.
if [ -z "${DBT_PROFILE_NAME}" ]; then
	echo 'Reading DBT_PROFILE_NAME from dbt_project.yml'
	DBT_PROFILE_NAME=$(python "${GITHUB_ACTION_PATH}/src/read_dbt_profile_name.py")
fi

# Print some debug info.
echo "dbt adapter: ${DBT_ADAPTER}"
echo "dbt profile name: ${DBT_PROFILE_NAME}"

# Replace the DBT_PROFILE_NAME for the wanted adapter with the actual profile name.
export DBT_PROFILES_DIR=${GITHUB_ACTION_PATH}/src/fake-dbt-profile
sed -i "s/DBT_PROFILE_NAME_${DBT_ADAPTER}/${DBT_PROFILE_NAME}/g" "${DBT_PROFILES_DIR}/profiles.yml"
if [ "${DEBUG_MODE}" = "true" ]; then
	cat "${DBT_PROFILES_DIR}/profiles.yml"
fi

# Generate the previous manifest.
git checkout "${GITHUB_BASE_REF}"
dbt ls
cp -r target target-previous
git checkout -

# Run impact analysis script.
DBT_ARTIFACT_STATE_PATH=target-previous python "${GITHUB_ACTION_PATH}/src/impact_analysis.py"
if [ "${DEBUG_MODE}" = "true" ]; then
	cat impact_analysis.md
fi

# Output a multiline string to an output parameter.
# Technique from https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#multiline-strings
set +x
EOF=$(dd if=/dev/urandom bs=10 count=1 status=none | base32)
{
	echo "IMPACT_ANALYSIS_MD<<$EOF"
	cat impact_analysis.md
	echo "$EOF"
} >> "$GITHUB_OUTPUT"
