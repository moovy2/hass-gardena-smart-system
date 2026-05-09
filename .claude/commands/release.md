Release a new version of the integration.

## Process

1. Pull the latest changes from remote: `git pull`

2. Determine the next version number based on the current version in `custom_components/gardena_smart_system/manifest.json` and the type of release requested (beta or stable).
   - Beta versions: `X.Y.Z-betaN` (increment N from the last beta, or start at beta1)
   - Stable versions: `X.Y.Z` (remove the beta suffix)

3. Update the version in `custom_components/gardena_smart_system/manifest.json`.

4. Commit with message: `chore: bump version to <version>`

5. Create a git tag matching the version exactly (e.g. `2.0.1-beta2` or `2.0.1`).

6. Push the commit and tag:
   ```
   git push && git push origin <tag>
   ```

## Tag format

Tags use the bare version number without any prefix (no `v`):
- `2.0.1-beta2` (not `v2.0.1-beta2`)
- `2.0.1` (not `v2.0.1`)

## Notes

- Always check existing tags with `git tag --list` to confirm the next version number.
- The version in manifest.json and the git tag must match exactly.
