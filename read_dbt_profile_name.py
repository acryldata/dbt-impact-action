import yaml
import pathlib

with pathlib.Path('dbt_project.yml').open() as f:
    dbt_project = yaml.safe_load(f)

print(dbt_project['profile'])
