"""Where the project's data files live.

A checkout uses its own directories. An installed copy,
such as the container image, sets SECONDLOOP_ROOT.
"""

import os
import pathlib

ROOT = pathlib.Path(
    os.environ.get(
        "SECONDLOOP_ROOT",
        pathlib.Path(__file__).resolve().parents[2],
    )
)
DATA = ROOT / "data"
