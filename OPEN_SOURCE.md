<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Open source

**nordctl is 100% open source** under the [MIT License](LICENSE).

## What that means

- You can read, modify, and redistribute the code under the license terms.
- There are **no proprietary blobs**, hidden analytics SDKs, or vendor lock-in in this repository.
- Dependencies are declared in `pyproject.toml` (core: PyYAML only; optional tray: pystray + Pillow).

## Forking & attribution

The MIT License lets you use, modify, and redistribute nordctl **without asking first**, as long as you **keep the copyright notice and LICENSE** in copies or substantial portions of the code.

**G4EA5** is the copyright holder. The author would like that name (and a link to [this repository](https://github.com/G4EA5/nordctl)) to stay visible when you share or ship nordctl — in `LICENSE`, README, or “About” text — rather than presenting the project as unrelated original work.

If you plan to **mirror the whole project**, **rebrand it**, or **distribute a packaged build** under another name, a quick message on [GitHub Issues](https://github.com/G4EA5/nordctl/issues) first is appreciated. That is **courtesy, not a license requirement**; MIT does not give anyone exclusive control over forks. It just helps avoid surprise clones and keeps credit clear.

Small personal patches, forks, and pull requests back upstream are always welcome — no need to ask for those.

## Verify for yourself

```bash
# PyPI or git install
pip install nordctl
pip show nordctl
python -c "import nordctl; print(nordctl.__file__)"

# Run tests
bash scripts/selftest.sh
```

## Privacy by design

See [LEGAL.md](LEGAL.md) and the in-app **Privacy manifest** (Security tab or `GET /api/privacy`).

nordctl does **not** phone home. Optional email alerts use **your** SMTP server and **your** recipient address only.

## Contributing

Bug reports and patches welcome on the project issue tracker. Do not commit secrets (SMTP passwords, Nord tokens) to config files you share publicly.
