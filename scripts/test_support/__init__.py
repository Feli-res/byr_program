"""Shared test helpers. Importing this package never starts services or runs checks."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
for directory in ['accounts-qa/python','design-qa/python','chat-qa/python']:
    package = ROOT / '.local' / directory
    if package.exists():sys.path.insert(0,str(package))
