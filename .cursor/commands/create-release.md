Update the version in `pyproject.toml` and commit the change.

- Bump version using uv:
   - For breaking changes: `uv version --bump major`
   - For new features: `uv version --bump minor`
   - For bug fixes: `uv version --bump patch`
-  `git add pyproject.toml uv.lock && git commit -m "Bump version to v$(uv version --short)"`
- `git tag v$(uv version --short) && git push origin v$(uv version --short)`
- `git push origin main`
