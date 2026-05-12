Update the CHANGELOG.md file with the latest changes.

## Process

1. Read the current `CHANGELOG.md`.

2. Add entries under the `## [Unreleased]` section at the top. If it doesn't exist, create it below the `# Changelog` header.

3. Categorize changes into the appropriate subsection:
   - **Breaking Changes** — removed entities, renamed services, changed behavior, migrations required
   - **Added** — new features, entities, services
   - **Fixed** — bug fixes
   - **Removed** — removed features (non-breaking, e.g. deprecated code cleanup)

4. Format:
   ```markdown
   ## [Unreleased]

   ### Breaking Changes

   - Description of breaking change — explain what the user needs to do to migrate

   ### Added

   - Description of new feature (#issue)

   ### Fixed

   - Description of bug fix (#issue)
   ```

5. Only include subsection headers that have entries.

6. Reference issue numbers where applicable.

7. Write concise, user-facing descriptions (not commit messages).

8. If entries already exist under `[Unreleased]`, append to the appropriate subsection — do NOT create a duplicate subsection.

## Notes

- The `[Unreleased]` section accumulates changes between releases. The `/release` skill handles renaming it to a version number at release time.
- This file is visible to users via HACS and GitHub releases.
- Breaking changes should explain what the user needs to do to migrate.
