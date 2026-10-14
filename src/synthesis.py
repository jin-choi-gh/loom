import argparse
import sys
from pathlib import Path

from composition import compose
from models import SynthesisError, Unit, Version


def show_version(version: Version) -> None:
    """Every line's atoms, each with its innermost unit in every schema."""
    names = list(version.schemata)

    def label(unit: Unit | None) -> str:
        return "–" if unit is None else f"{unit.rank.name} {unit.local_id}"

    print(f"{'atom':12}" + "".join(f"{name:22}" for name in names))
    for line, atoms in version.lines():
        print(f"── {line.id}: {line.text}")
        for atom in atoms:
            cells = [label(atom.innermost.get(name)) for name in names]
            print(f"{atom.text!r:12}" + "".join(f"{cell:22}" for cell in cells))


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Create a textual complex.")
    ap.add_argument(
        "files", nargs="+", type=Path, help="The representations of one text"
    )
    args = ap.parse_args(argv)

    try:
        version = compose(args.files)
        show_version(version)

    except SynthesisError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
