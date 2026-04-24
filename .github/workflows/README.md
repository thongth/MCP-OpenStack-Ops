# GitHub Workflows Overview

Thu muc nay chua GitHub Actions workflows cho project.

## Workflow hien tai

- `pypi-publish.yml`
- Trigger: push tag (`on.push.tags: ["*"]`)
- Muc dich: build package va publish len TestPyPI/PyPI

## Pipeline tom tat

1. Checkout source va lay version tu ten tag.
2. Inject version vao `pyproject.toml`.
3. Build distribution (`python -m build`).
4. Upload artifact `dist/`.
5. Publish sang TestPyPI.
6. Publish sang PyPI.

## Luu y van hanh

- Workflow su dung trusted publishing (OIDC) qua `id-token: write`.
- Environment names: `testpypi`, `pypi`.
- Can tao tag hop le de kick release pipeline.

