from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
from .utils import read_json, write_json, resolve_paths, normalize_char, load_config, now_ts
from .live_sync import live_job_create, live_job_update, to_media_url

def _extract_age(age_str, use_midpoint: bool = False) -> int:
    """Extract numeric age from various formats like '60s', '64', 'late 40s', '50-60', etc.

    Args:
        age_str: Age string to parse
        use_midpoint: If True and range detected, return midpoint instead of first number
    """
    if not age_str:
        return 0
    age_str = str(age_str).lower().strip()

    import re

    # Handle explicit ranges like "50-60" or "50-58"
    range_match = re.match(r'(\d+)\s*[-–]\s*(\d+)', age_str)
    if range_match:
        low, high = int(range_match.group(1)), int(range_match.group(2))
        return (low + high) // 2 if use_midpoint else low

    # Find all numbers
    nums = re.findall(r'\d+', age_str)
    if nums:
        age = int(nums[0])
        # Adjust for decade descriptors
        if 'late' in age_str:
            age += 7
        elif 'mid' in age_str:
            age += 5
        elif 'early' in age_str:
            age += 2
        return age
    return 0


def _score_actor(character: dict, actor: dict) -> Tuple[int, List[str]]:
    """
    Improved actor scoring with actual age matching and character-type analysis.
    Returns score 0-100 and list of reasons.
    """
    reasons = []
    score = 0

    # === GENDER MATCH (Required) ===
    cg = (character.get("gender") or "").lower()
    ag = (actor.get("gender") or actor.get("sex") or "").lower()
    if cg and ag:
        if cg == ag:
            score += 25
            reasons.append("gender_match")
        else:
            score -= 50  # Heavy penalty for gender mismatch
            reasons.append("gender_mismatch")

    # === AGE MATCHING (Actual comparison) ===
    # Use midpoint for more accurate age comparison
    c_age = _extract_age(character.get("age") or character.get("age_range"), use_midpoint=True)
    a_age = _extract_age(actor.get("age") or actor.get("age_range"), use_midpoint=True)

    if c_age > 0 and a_age > 0:
        age_diff = abs(c_age - a_age)
        if age_diff <= 5:
            score += 30
            reasons.append(f"age_exact:{c_age}~{a_age}")
        elif age_diff <= 10:
            score += 20
            reasons.append(f"age_close:{c_age}~{a_age}")
        elif age_diff <= 15:
            score += 10
            reasons.append(f"age_acceptable:{c_age}~{a_age}")
        else:
            score -= 15
            reasons.append(f"age_mismatch:{c_age}vs{a_age}")

    # === CHARACTER TYPE MATCHING ===
    char_name = (character.get("name") or "").lower()
    char_desc = (character.get("description") or character.get("descriptor") or "").lower()
    # Handle specialty as list or string
    spec = actor.get("type") or actor.get("specialty") or ""
    actor_type = " ".join(spec).lower() if isinstance(spec, list) else str(spec).lower()
    actor_name = (actor.get("name") or "").lower()

    # Elderly/senior character markers (50+ characters)
    elderly_markers = ["elderly", "matriarch", "patriarch", "grandmother", "grandfather",
                       "old", "aged", "senior", "dowager", "retired"]
    # Note: removed "lady" and "lord" as they indicate title, not age
    is_elderly_char = any(m in char_name or m in char_desc for m in elderly_markers) or c_age >= 50

    # Young character markers
    young_markers = ["young", "youth", "teen", "child", "boy", "girl", "student"]
    is_young_char = any(m in char_name or m in char_desc for m in young_markers) or (0 < c_age <= 25)

    # Actor age category - use midpoint age for categorization
    actor_is_elderly = a_age >= 50  # Lowered from 55 to match 50+ character requirement
    actor_is_young = a_age <= 28

    # Bonus for matching age category
    if is_elderly_char and actor_is_elderly:
        score += 20
        reasons.append("type_elderly_match")
    elif is_young_char and actor_is_young:
        score += 20
        reasons.append("type_young_match")
    elif is_elderly_char and not actor_is_elderly:
        score -= 25
        reasons.append("type_elderly_mismatch")
    elif is_young_char and not actor_is_young:
        score -= 25
        reasons.append("type_young_mismatch")

    # === ETHNICITY/CULTURAL MATCHING ===
    ce = (character.get("ethnicity") or "").lower()
    ae = (actor.get("ethnicity") or "").lower()

    # Cultural proximity groups for matching
    ethnicity_groups = {
        "european": ["british", "english", "european", "caucasian", "white", "scandinavian",
                     "italian", "french", "german", "spanish", "irish", "scottish", "welsh"],
        "asian": ["asian", "chinese", "japanese", "korean", "vietnamese", "thai", "filipino"],
        "african": ["african", "black", "nigerian", "kenyan", "ethiopian"],
        "hispanic": ["hispanic", "latino", "latina", "mexican", "spanish", "portuguese", "brazilian"],
        "middle_eastern": ["middle eastern", "arab", "persian", "indian", "pakistani", "turkish"]
    }

    def get_ethnicity_group(eth: str) -> str:
        for group, keywords in ethnicity_groups.items():
            if any(kw in eth for kw in keywords):
                return group
        return "unknown"

    if ce and ae:
        c_group = get_ethnicity_group(ce)
        a_group = get_ethnicity_group(ae)

        if ce in ae or ae in ce:
            # Exact match
            score += 20
            reasons.append(f"ethnicity_exact:{ce}={ae}")
        elif c_group == a_group and c_group != "unknown":
            # Same cultural group (British = European, etc.)
            score += 10
            reasons.append(f"ethnicity_group:{c_group}")
        elif c_group != "unknown" and a_group != "unknown" and c_group != a_group:
            # Different cultural groups - penalty
            score -= 20
            reasons.append(f"ethnicity_mismatch:{ce}({c_group})vs{ae}({a_group})")

    # === HEADSHOT AVAILABLE ===
    if actor.get("headshot_path") or actor.get("headshot_url"):
        score += 10
        reasons.append("has_headshot")

    # Stabilize score
    score = max(0, min(100, score))
    return score, reasons

def cast_agent_run(project: str, overwrite: bool=False, repo_root: str | Path | None = None) -> dict:
    p = resolve_paths(project, repo_root=repo_root)
    cfg = load_config(p.repo_root)
    proj_dir = p.project_dir

    job = live_job_create(project, "auto-cast", {"project": project, "overwrite": overwrite}, repo_root=p.repo_root)
    job_id = job["job"]["job_id"]
    live_job_update(project, job_id, "running", repo_root=p.repo_root)

    story_bible = read_json(proj_dir / "story_bible.json", default=None)
    if not story_bible:
        live_job_update(project, job_id, "failed", {"error": "Missing story_bible.json"}, repo_root=p.repo_root)
        return {"success": False, "blocking": ["missing_story_bible"], "warnings": [], "artifacts_written": []}

    characters = story_bible.get("characters") or []
    if isinstance(characters, dict):
        characters = list(characters.values())
    if not characters:
        live_job_update(project, job_id, "failed", {"error": "No characters in story_bible"}, repo_root=p.repo_root)
        return {"success": False, "blocking": ["no_characters"], "warnings": [], "artifacts_written": []}

    cast_map_path = proj_dir / "cast_map.json"
    existing_cast = read_json(cast_map_path, default={})

    # V17: Merge strategy - preserve approved entries
    approved_chars = set()
    if existing_cast.get("_approved"):
        for cname, cdata in existing_cast.items():
            if not cname.startswith("_") and isinstance(cdata, dict):
                if cdata.get("_locked") or cdata.get("approved"):
                    approved_chars.add(cname.upper())

    if cast_map_path.exists() and not overwrite and not approved_chars:
        # Only skip if exists and no approved chars to preserve
        live_job_update(project, job_id, "completed", repo_root=p.repo_root)
        return {"success": True, "message": "Cast map already exists", "artifacts_written": [str(cast_map_path)]}

    # V17: Find all characters from shot_plan too (for CLERK, etc.)
    shot_plan = read_json(proj_dir / "shot_plan.json", default={})
    shot_plan_chars = set()
    for shot in shot_plan.get("shots", []):
        chars = shot.get("characters", [])
        if isinstance(chars, str):
            chars = [chars]
        shot_plan_chars.update([c.upper() for c in chars if c])

    # V17: EXTRAS POOL markers for generic/minor characters
    extras_pool_keywords = ["CLERK", "GUARD", "SERVANT", "MAID", "VILLAGER", "CROWD", "EXTRAS", "PASSERBY"]

    actor_lib = read_json(p.actor_library, default=None)
    if not actor_lib:
        live_job_update(project, job_id, "failed", {"error": "Missing ai_actors_library.json"}, repo_root=p.repo_root)
        return {"success": False, "blocking": ["missing_actor_library"], "warnings": [], "artifacts_written": []}

    # Actor library can be list or dict
    actors = actor_lib if isinstance(actor_lib, list) else actor_lib.get("actors") or list(actor_lib.values())
    policy = cfg["policy"]["casting"]
    min_score = int(policy.get("min_fit_score", 55))
    fallback_mode = policy.get("fallback_mode", "best_available")
    placeholder_actor = policy.get("placeholder_actor", "UNKNOWN_ACTOR")

    out: Dict[str, Any] = {"_meta": {"generated_at": now_ts(), "version": cfg.get("version", "16.7")}}
    warnings = []
    blocking = []
    used_actor_ids = set()  # V16.7: Track used actors to prevent duplicates

    # V17: Preserve approved entries in output
    for cname, cdata in existing_cast.items():
        if cname.startswith("_"):
            continue
        if cname.upper() in approved_chars and isinstance(cdata, dict):
            out[cname] = cdata
            actor_id = cdata.get("ai_actor_id") or cdata.get("ai_actor")
            if actor_id:
                used_actor_ids.add(actor_id)
            warnings.append(f"preserved_approved:{cname}")

    # Build character list from story_bible + shot_plan
    story_bible_char_names = set()
    for ch in characters:
        cname = normalize_char(ch.get("name") or ch.get("character") or "")
        if cname:
            story_bible_char_names.add(cname.upper())

    # V17: Helper to check if short name is alias of full name (e.g., "EVELYN" -> "EVELYN RAVENCROFT")
    def is_alias_of(short_name: str, full_names: set) -> bool:
        short_upper = short_name.upper()
        for full in full_names:
            if full.startswith(short_upper + " ") or full == short_upper:
                return True
        return False

    # V17: Add EXTRAS POOL for characters in shot_plan but not in story_bible
    for sp_char in shot_plan_chars:
        sp_upper = sp_char.upper()
        # Skip if exact match in story_bible
        if sp_upper in story_bible_char_names:
            continue
        # Skip if it's an alias of a story_bible character (e.g., "EVELYN" -> "EVELYN RAVENCROFT")
        if is_alias_of(sp_char, story_bible_char_names):
            continue

        norm_char = normalize_char(sp_char)
        if norm_char.upper() in approved_chars:
            continue  # Already preserved

        # Check if it's a generic/extras character
        is_extras = any(kw in norm_char.upper() for kw in extras_pool_keywords)
        if is_extras:
            out[norm_char] = {
                "ai_actor": "EXTRAS POOL",
                "ai_actor_id": "extras",
                "gender": "unknown",
                "headshot_url": "",
                "reference_url": "",
                "character_reference_url": "",
                "fit_score": 100,
                "reasons": ["extras_pool_minor_character"],
                "is_extras_pool": True,
            }
            warnings.append(f"extras_pool:{norm_char}")

    for ch in characters:
        cname = normalize_char(ch.get("name") or ch.get("character") or "")
        if not cname:
            continue

        # V17: Skip if already handled (approved or extras)
        if cname.upper() in approved_chars or cname in out:
            continue

        best = None
        best_score = -1
        best_reasons = []

        for a in actors:
            # V16.7: Skip already-used actors
            actor_id = a.get("id") or a.get("name")
            if actor_id in used_actor_ids:
                continue
            s, rs = _score_actor(ch, a)
            if s > best_score:
                best = a
                best_score = s
                best_reasons = rs

        if best is None:
            blocking.append(f"no_actor_candidates:{cname}")
            continue

        if best_score < min_score:
            if fallback_mode == "strict":
                blocking.append(f"below_threshold:{cname}:{best_score}")
                continue
            elif fallback_mode == "placeholder":
                out[cname] = {"ai_actor": placeholder_actor, "ai_actor_id": None, "fit_score": best_score, "reasons": best_reasons, "headshot_url": ""}
                warnings.append(f"placeholder_used:{cname}:{best_score}")
                continue
            else:
                warnings.append(f"below_threshold_but_used_best:{cname}:{best_score}")

        # Build headshot URL
        headshot = best.get("headshot_url") or ""
        hp = best.get("headshot_path")
        if hp:
            headshot = to_media_url(str(Path(hp).resolve()), repo_root=p.repo_root)

        # V16.7: Mark actor as used
        used_actor_ids.add(best.get("id") or best.get("name"))

        # Build reference_url (same as headshot for consistency)
        reference_url = headshot
        if not reference_url and hp:
            reference_url = to_media_url(str(Path(hp).resolve()), repo_root=p.repo_root)

        out[cname] = {
            "ai_actor": best.get("name") or best.get("ai_actor") or best.get("actor_name") or "Unknown",
            "ai_actor_id": best.get("id") or best.get("ai_actor_id"),
            "gender": (best.get("gender") or best.get("sex") or "unknown"),
            "headshot_url": headshot,
            "reference_url": reference_url,
            "character_reference_url": reference_url,
            "fit_score": int(best_score),
            "reasons": best_reasons,
            "is_extras_pool": False,
        }

    # V17: Build aliases mapping (short name -> full name)
    # This allows shot_plan "EVELYN" to resolve to "EVELYN RAVENCROFT"
    aliases = {}
    cast_names = [k for k in out.keys() if not k.startswith("_")]
    for sp_char in shot_plan_chars:
        sp_upper = sp_char.upper()
        # Skip if exact match already exists
        if sp_upper in cast_names:
            continue
        # Find the full name this is an alias for
        for full_name in cast_names:
            if full_name.startswith(sp_upper + " "):
                aliases[sp_upper] = full_name
                break

    if aliases:
        out["_aliases"] = aliases

    write_json(cast_map_path, out)
    report_path = proj_dir / "cast_report.json"
    write_json(report_path, {"blocking": blocking, "warnings": warnings, "min_score": min_score})

    status = "completed" if not blocking else "failed"
    live_job_update(project, job_id, status, {"blocking": blocking, "warnings": warnings}, repo_root=p.repo_root)
    return {
        "success": status == "completed",
        "blocking": blocking,
        "warnings": warnings,
        "artifacts_written": [str(cast_map_path), str(report_path)]
    }
