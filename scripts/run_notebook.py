"""Execute a notebook headlessly, in place (see notebooks/README.md).

Notebooks in this project are a presentation layer over committed CSVs, which
means they are only trustworthy if they still *run*. A notebook whose stored
output was produced by code that no longer exists is worse than no notebook: it
looks like evidence.

    python scripts/run_notebook.py notebooks/03_results.ipynb
    python scripts/run_notebook.py notebooks/03_results.ipynb --check

`--check` executes without saving, which is the form to put in CI: it proves the
notebook runs against the current library and the current CSVs without creating
a diff on every run.

`jupyter nbconvert --execute` does the same job; this exists so the invocation is
one short line that does not vary by jupyter version, and so the failure message
names the cell.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def run(path: Path, *, save: bool = True, timeout: int = 600) -> int:
    try:
        import nbformat
        from nbclient import NotebookClient
        from nbclient.exceptions import CellExecutionError
    except ImportError:
        print(
            "notebook toolchain missing. Install it with:\n"
            "    pip install nbformat nbclient ipykernel pandas matplotlib",
            file=sys.stderr,
        )
        return 2

    notebook = nbformat.read(path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=timeout,
        kernel_name="python3",
        # Run with the repository root as the working directory so `mfstnet`
        # imports and the relative paths to experiments/results/ both resolve,
        # whether the notebook is launched from the root or from notebooks/.
        resources={"metadata": {"path": str(path.parent)}},
    )

    try:
        client.execute()
    except CellExecutionError as error:
        print(f"\n{path.name} failed to execute:\n{error}", file=sys.stderr)
        return 1

    if save:
        nbformat.write(notebook, path)
        print(f"executed and saved {path}")
    else:
        print(f"executed {path} (not saved)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("notebook", type=Path)
    parser.add_argument(
        "--check", action="store_true",
        help="execute without saving — the form to use in CI",
    )
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)

    if not args.notebook.exists():
        raise SystemExit(f"no such notebook: {args.notebook}")
    return run(args.notebook, save=not args.check, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
