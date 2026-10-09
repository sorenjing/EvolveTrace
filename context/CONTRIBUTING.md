# Contributing

Use Python 3.11 or newer and keep runtime code standard-library only.

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

Add a failing test before changing behavior. Keep scanning offline and bounded to recognized metadata. Do not weaken marker validation or overwrite user-owned entry files.

Open focused pull requests with a short explanation of the user-visible behavior and verification performed.

