"""Run the complete Chinese-comment analysis pipeline in sequence."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    for name in ("01_prepare_data.py", "02_topic_analysis.py", "03_sentiment_analysis.py", "04_semantic_network.py", "05_build_report.py"):
        print(f"\n=== Running {name} ===")
        subprocess.run([sys.executable, str(ROOT / name)], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
