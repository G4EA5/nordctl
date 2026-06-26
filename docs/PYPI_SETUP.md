<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# PyPI trusted publishing setup

The **Publish to PyPI** workflow failed on the v0.2.0 release because PyPI has no **trusted publisher** for this repository yet. That is expected — the `.deb` on [GitHub Releases](https://github.com/G4EA5/nordctl/releases) is the primary install path for now.

## Why it failed

```
invalid-publisher: valid token, but no corresponding publisher
```

GitHub Actions sent these claims; PyPI must have a matching publisher configured:

| Claim | Value |
|--------|--------|
| Repository owner | `G4EA5` |
| Repository name | `nordctl` |
| Workflow filename | `publish-pypi.yml` |
| Environment name | *(leave blank)* |

## One-time setup on PyPI

1. Log in at [pypi.org](https://pypi.org/) (create an account if needed).
2. **Account settings → Publishing** → add a **pending publisher** (or open an existing `nordctl` project → **Publishing**).
3. Set:
   - **PyPI Project Name:** `nordctl`
   - **Owner:** `G4EA5`
   - **Repository name:** `nordctl`
   - **Workflow name:** `publish-pypi.yml`
   - **Environment name:** *(empty)*
4. Save. The first successful publish creates the project if it does not exist yet.

## Publish manually (test)

In GitHub: **Actions → Publish to PyPI → Run workflow**.

Or locally with an API token (not recommended for routine use):

```bash
python -m build
twine upload dist/*
```

## Enable auto-publish on Release (optional)

After a manual workflow run succeeds, edit `.github/workflows/publish-pypi.yml` and uncomment:

```yaml
on:
  workflow_dispatch:
  release:
    types: [published]
```

Future GitHub Releases will then upload wheels/sdists to PyPI automatically.
