# Usage

## Run from source

```powershell
python .\grepper.py
```

## Install from GitHub (optional)

If you add this repository to GitHub, you can install it directly with pip:

```powershell
python -m pip install "git+https://github.com/atifafzal786/Grepper-Utility.git"
```

## Tips

- If you have VS Code installed, Grepper will try to open files at a specific line using `code -g`.
- On Windows Grepper will use the default opener via `os.startfile`.

## Run (GUI)

Run the Tkinter GUI from the repository root:

```powershell
python .\grepper.py
```

The UI lets you:
- Choose a directory to scan
- Filter by filename patterns (glob)
- Search file contents with plain text or regular expressions
- Respect `.gitignore` rules and skip hidden files

## Use as a library

Grepper exposes utility functions for small automation scripts. Example:

```python
from grepper import fmt_size, load_gitignore_rules

print(fmt_size(2048))
rules = load_gitignore_rules('.')
```

## Examples and screenshots

Example UI screenshots are in `doc/images/` and show search results and a preview pane.

