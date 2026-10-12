"""Run the full English-comment analysis in dependency order."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STAGES = ["01_prepare_data.py", "02_topic_analysis.py", "03_sentiment_analysis.py", "04_semantic_network.py", "05_build_report.py"]


def main() -> None:
    for stage in STAGES:
        print(f"\n=== Running {stage} ===")
        subprocess.run([sys.executable, str(ROOT / stage)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
