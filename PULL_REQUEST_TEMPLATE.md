## Summary

<!-- One paragraph describing what this PR does and why. Be specific. -->

## Type of change

- [ ] `feat` — new feature
- [ ] `fix` — bug fix
- [ ] `refactor` — code change without new feature or bug fix
- [ ] `docs` — documentation only
- [ ] `test` — adding or correcting tests
- [ ] `chore` — build, CI, or tooling changes
- [ ] `security` — security-relevant change

## Scope

- [ ] `backend`
- [ ] `frontend`
- [ ] `omniverse` (OpenUSD / Omniverse integration)
- [ ] `sim-bridge` (solver adapter layer)
- [ ] `ci` / `infra`
- [ ] `docs`

## Checklist

### Code quality
- [ ] Code follows project style (ruff / eslint passing locally)
- [ ] Type annotations added / updated (mypy / tsc clean)
- [ ] No commented-out code or debug statements in diff

### Testing
- [ ] New tests written for new functionality
- [ ] All existing tests pass locally (`pytest` / `vitest`)
- [ ] Coverage not decreased below 80%

### Security
- [ ] No secrets, credentials, or API keys introduced into the codebase
- [ ] No new dependencies added without reviewing for CVEs (`safety check`)
- [ ] User input is validated via Pydantic schemas before use

### Architecture
- [ ] If this PR changes a significant architectural decision, an ADR has been created or updated in `docs/adr/`
- [ ] ADR reference (if applicable): `ADR-00X — …`

### Documentation
- [ ] README updated if new environment variables or setup steps are required
- [ ] Inline docstrings updated for any modified public functions / classes

## Testing instructions

<!-- Exact steps to verify this PR manually, if applicable. -->

1.
2.
3.

## Related issues

<!-- Closes #N or references #N -->
