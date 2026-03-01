# Docs and GitHub Pages

`spytial-py` already has a MkDocs site and a GitHub Pages deployment workflow. The practical work is maintaining the docs content and keeping the deployment path explicit.

## Local docs workflow

Install the docs dependencies:

```bash
python -m pip install -e ".[docs]"
```

Run a local preview server:

```bash
mkdocs serve
```

Build the site exactly the way CI does:

```bash
mkdocs build --strict
```

## Deployment

The docs site is deployed by `.github/workflows/gh-pages.yml`.

That workflow currently:

- runs on pushes to `main` or `master`
- installs `.[docs]`
- builds the site with `mkdocs build --strict`
- publishes the generated `site/` directory to GitHub Pages

With the current repository name, the expected GitHub Pages URL is:

`https://sidprasad.github.io/cnd-py/`

## How `spytial-clrs` fits in

`spytial-clrs` should be treated as the examples and gallery source, while this repo remains the canonical home for Python API docs and contributor docs.

That split keeps ownership clear:

- API and behavior docs live here
- notebook-heavy walkthroughs and richer examples live there
