Release a new version of the integration.

## Process

1. Pull the latest changes from remote: `git pull`

2. Determine the next version number based on the current version in `custom_components/gardena_smart_system/manifest.json` and the type of release requested (beta or stable).
   - Beta versions: `X.Y.Z-betaN` (increment N from the last beta, or start at beta1)
   - Stable versions: `X.Y.Z` (remove the beta suffix)
   - If `CHANGELOG.md` has a `### Breaking Changes` section under `[Unreleased]`, bump the major version.

3. Update the version in `custom_components/gardena_smart_system/manifest.json`.

4. Update `CHANGELOG.md`:
   - Replace `## [Unreleased]` with `## [<version>] - YYYY-MM-DD` (today's date).
   - Add a fresh empty `## [Unreleased]` section above it.

5. Commit with message: `chore: bump version to <version>`

6. Create a git tag matching the version exactly (e.g. `2.0.1-beta2` or `2.0.1`).

7. Push the commit and tag:
   ```
   git push && git push origin <tag>
   ```

8. Create the GitHub release with the content of the changelog section as body:
   - For beta releases:
     ```
     gh release create <tag> --generate-notes --prerelease --title "Release <tag>"
     ```
   - For stable releases:
     ```
     gh release create <tag> --notes "$(changelog section content)" --latest --title "Release <tag>"
     ```
     Use the changelog section for that version as release notes (formatted as markdown). Fall back to `--generate-notes` if the section is empty.

## Tag format

Tags use the bare version number without any prefix (no `v`):
- `2.0.1-beta2` (not `v2.0.1-beta2`)
- `2.0.1` (not `v2.0.1`)

## Notes

- Always check existing tags with `git tag --list` to confirm the next version number.
- The version in manifest.json and the git tag must match exactly.
- If `CHANGELOG.md` has no `[Unreleased]` section or it's empty, warn the user before proceeding.
