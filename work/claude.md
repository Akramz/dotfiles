# Work machine

## Packages

A managed work Mac can block `pypi.org` and `files.pythonhosted.org`. Install Python packages from the approved package proxy instead.

- Set the proxy as the default index in `~/.config/uv/uv.toml` (MANUAL.md §7), so plain `uv add` / `uv sync` just works. That file holds the URL.
- If a project pins its own index (public repos pin canonical PyPI so the lock file stays portable), do not edit the pin — set `UV_DEFAULT_INDEX` to the proxy for that command.
- A failed install or a hang reaching PyPI means the index, not the package.

## GitHub credentials

With a personal and a corporate GitHub account, the macOS keychain helper can hand back the wrong one, and a push fails with a misleading **"Repository not found"**. The fix is a repo-local `credential.helper = !gh auth git-credential`.
