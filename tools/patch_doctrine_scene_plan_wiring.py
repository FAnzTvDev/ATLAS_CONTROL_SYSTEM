#!/usr/bin/env python3
"""
Patch orchestrator_server.py to wire doctrine scene_plans into pre-generation context.
This makes EXECUTIVE_LAW_02 receive actual scene_plan data instead of empty dict.

What it does:
1. Adds scene_plan loading from reports/doctrine_scene_plans.json
2. Injects scene_plan into _doc_context dict

Run: python3 tools/patch_doctrine_scene_plan_wiring.py
"""
import re

SERVER_PATH = "/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/orchestrator_server.py"

with open(SERVER_PATH) as f:
    content = f.read()

# Find the _doc_context block and inject scene_plan
old_context = '''                _doc_context = {
                    "cast_map": cast_map,
                    "scene_manifest": data.get("scene_manifest", {}),
                    "all_known_characters": list(
                        k for k, v in cast_map.items()
                        if isinstance(v, dict) and not k.startswith("_") and not v.get("_is_alias_of")
                    ),
                }'''

new_context = '''                # V24.2.5: Load doctrine scene plans for EXECUTIVE_LAW_02 compliance
                _doctrine_scene_plans = {}
                _dsp_path = project_path / "reports" / "doctrine_scene_plans.json"
                if _dsp_path.exists():
                    try:
                        import json as _dsp_json
                        with open(_dsp_path) as _dsp_f:
                            _doctrine_scene_plans = _dsp_json.load(_dsp_f)
                        logger.info(f"[DOCTRINE] Loaded scene plans: {len(_doctrine_scene_plans)} scenes")
                    except Exception as _dsp_err:
                        logger.warning(f"[DOCTRINE] Scene plan load failed: {_dsp_err}")
                _doc_context = {
                    "cast_map": cast_map,
                    "scene_manifest": data.get("scene_manifest", {}),
                    "scene_plan": _doctrine_scene_plans,
                    "all_known_characters": list(
                        k for k, v in cast_map.items()
                        if isinstance(v, dict) and not k.startswith("_") and not v.get("_is_alias_of")
                    ),
                }'''

if old_context in content:
    content = content.replace(old_context, new_context)
    with open(SERVER_PATH, "w") as f:
        f.write(content)
    print("PATCHED: doctrine scene_plan wired into pre-generation context")
    print("  - Loads from reports/doctrine_scene_plans.json")
    print("  - EXECUTIVE_LAW_02 will now receive actual scene plan data")
else:
    print("WARNING: Could not find exact match for _doc_context block")
    print("  The orchestrator may have already been patched or the code has changed")
    print("  Manual inspection needed at ~line 20334")
