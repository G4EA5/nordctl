<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Open source

**nordctl is 100% open source** under the [MIT License](LICENSE).

## What that means

- You can read, modify, and redistribute the code under the license terms.
- There are **no proprietary blobs**, hidden analytics SDKs, or vendor lock-in in this repository.
- Dependencies are declared in `pyproject.toml` (core: PyYAML only; optional tray: pystray + Pillow).

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
