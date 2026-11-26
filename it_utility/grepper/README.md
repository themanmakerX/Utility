# Grepper

Grepper is a lightweight desktop search utility for finding text, files, and folders. It provides a compact Tkinter interface, optional ripgrep acceleration, live search metrics, previews, activity logs, and CSV export without requiring third-party Python packages.

## Features

- Search file contents using plain text or regular expressions.
- Find files and folders by name.
- Run multiple independent searches in tabs.
- Use include/exclude globs, size limits, depth limits, case matching, whole-word matching, and context lines.
- Skip hidden paths and apply a practical subset of root `.gitignore` rules.
- Use `ripgrep` automatically when available, with a built-in Python fallback.
- Pause, resume, cancel, and monitor searches with clear visual states.
- Preview matching lines with configurable surrounding context.
- Open results in VS Code, Notepad++, gVim, or the system default application.
- Copy paths or matched text and export visible results to CSV.
- Save the latest search defaults between sessions.

## Requirements

- Python 3.10 or newer
- Tkinter (included with standard Windows and most standard Python installations)
- Optional: [`ripgrep`](https://github.com/BurntSushi/ripgrep) available as `rg` on `PATH`

Grepper itself uses only the Python standard library. Pytest is required only for running the tests.

## Run from source

```powershell
cd path\to\grepper
python .\grepper.py
```

## Install as a command

From the project directory:

```powershell
python -m pip install .
grepper
```

Or install straight from GitHub:

```powershell
python -m pip install "git+https://github.com/themanmakerX/Utility.git#subdirectory=it_utility/grepper"
```

For editable development installs:

```powershell
python -m pip install -e .
```

## Search modes

Select a mode from the dropdown beside **Choose folder**.

### Text

Searches inside readable text files. Text mode supports regex, case sensitivity, whole-word matching, context previews, first-match-per-file behavior, file-type filtering, and optional ripgrep acceleration.

### File

Searches filenames. An optional content filter can require a matching file to also contain a text or regex pattern.

### Folder

Searches folder names. An optional content filter can inspect files directly inside each matching folder.

## Interface workflow

1. Choose a folder.
2. Select Text, File, or Folder mode.
3. Enter the active mode's search pattern.
4. Open **Advanced filters** only when additional control is required.
5. Select **Start search**.
6. Inspect results on the left and previews or activity details on the right.

The Results/Details splitter is draggable. **Focus workspace** hides the search controls temporarily so both panels can use more space.

### Advanced filters

The collapsed Advanced filters panel contains:

- Include and exclude glob patterns separated by semicolons
- Maximum file size in MB (`0` means unlimited)
- Maximum directory depth (blank means unlimited)
- Hidden-path and `.gitignore` controls
- Regex, case-sensitive, and whole-word matching
- First match per file
- Preview context-line count
- Ripgrep selection when `rg` is available

### Search action states

| State | Start search | Pause/Resume | Cancel |
|---|---|---|---|
| Idle | Blue, enabled | Grey, disabled | Grey, disabled |
| Running | Grey, disabled | Amber, enabled | Red, enabled |
| Paused | Grey, disabled | Green Resume | Red, enabled |
| Cancelling | Disabled | Disabled | Disabled |

Elapsed time, visible file counts, match counts, and the progress animation freeze while paused. Paused duration is excluded when the search resumes. The Python backend pauses cooperatively at safe checkpoints. With ripgrep, Grepper pauses consumption of ripgrep output; the external process may continue briefly until its output pipe applies backpressure.

## Result actions

- Select a text result to open its context preview.
- Double-click a result to open it.
- Right-click to copy a path or line, open the file, or open its directory.
- Use **More > Export CSV** to export the current result table.

When possible, Grepper opens text matches at the correct line using:

1. VS Code (`code -g`)
2. Notepad++
3. gVim
4. The operating system's default application

## Tabs and shortcuts

- `Ctrl+N`: create a search tab
- `Ctrl+W`: close the active search tab
- Click `+`: create a search tab
- Right-click a tab: open its close action

Closing a running tab safely cancels its worker before removing the UI.

## Settings and logging

Search defaults are stored outside the repository:

- Windows: `%APPDATA%\Grepper\settings.json`
- Other platforms: the `Grepper/settings.json` path under the resolved home/config location

Optional file logging can be toggled from the **More** menu. The generated `search.log` file is ignored by Git.

## Use utility functions from Python

```python
from grepper import fmt_size, load_gitignore_rules

print(fmt_size(2048))
rules = load_gitignore_rules(".")
print(rules)
```

See [`grepper_examples/example_usage.py`](grepper_examples/example_usage.py) for a runnable example.

## Development and verification

```powershell
python -m py_compile .\grepper.py
python -m pytest -q
```

The project intentionally keeps runtime dependencies at zero. Keep generated caches, build output, virtual environments, and logs out of source control.

## Project structure

```text
grepper.py                 Main application and library module
grepper_examples/          Small library-usage example
tests/                     Automated utility and regression tests
.github/                   CI, publishing, contribution, and community files
pyproject.toml             Package metadata and console entry point
requirements.txt           Runtime dependency statement
CHANGELOG.md               Unreleased and released changes
LICENSE                    MIT license
```

## Known limitations

- `.gitignore` support is intentionally a practical subset rather than a complete Git implementation.
- Binary detection uses a fast null-byte check and may not classify every unusual format perfectly.
- Folder content filtering checks files directly inside matching folders rather than recursively searching their descendants.
- Some unreadable files and decoding errors are skipped so a large search can continue.

## Contributing

See [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md). Bug fixes, focused performance improvements, tests, and documentation corrections are welcome.

## License

Grepper is available under the [MIT License](LICENSE).
