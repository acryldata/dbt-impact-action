

TODO Build out a better development guide here.


## Releases

When cutting a new release, use GitHub's UI for `Draft a Release`.
- Do **not** check "publish this action to the GitHub marketplace". The `v1` tag is the only one that should be published there.
- Set the tag name to be `v1.x.y` - create a new tag on publish.

We have a CI job that will automatically update the clean `v1` tag when the `v1.x.y` tag is published.
