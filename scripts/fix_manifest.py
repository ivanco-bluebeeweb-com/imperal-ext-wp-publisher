#!/usr/bin/env python3
"""Workaround for an imperal-sdk build/validate mismatch (present in 5.9.4):
`imperal build` emits fields (panels: icon/refresh/center_overlay; secrets:
scope/env_fallback) that the manifest schema rejects. Run after every build:

    venv-wp/bin/python scripts/fix_manifest.py

Allowed field sets are read from the installed SDK's own Pydantic schema, so
the script stays correct when the schema gains fields.
"""

import json
import sys
from pathlib import Path

from imperal_sdk import manifest_schema

ALLOWED = {
    "panels": set(manifest_schema.Panel.model_fields),
    "secrets": set(manifest_schema.SecretDecl.model_fields),
}

manifest_path = Path(sys.argv[1] if len(sys.argv) > 1 else "src/imperal.json")
manifest = json.loads(manifest_path.read_text())

removed = []
for section, allowed_fields in ALLOWED.items():
    for entry in manifest.get(section, []):
        label = entry.get("panel_id") or entry.get("name") or "?"
        for key in list(entry):
            if key not in allowed_fields:
                removed.append(f"{section}.{label}.{key}")
                del entry[key]

manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
print(f"Stripped {len(removed)} field(s): {', '.join(removed) or 'nothing to do'}")
