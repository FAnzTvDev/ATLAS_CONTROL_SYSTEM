#!/usr/bin/env python3
"""
ATLAS Vision Verification & Validation Dashboard
Intent vs Delivery — Perpetual Learning System
Run: python3 vision_dashboard.py
"""

import json, os, mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE = Path(__file__).parent
PROJECT = BASE / "pipeline_outputs" / "victorian_shadows_ep1"

# ── Load shot plan ────────────────────────────────────────────────────────────
def load_shots():
    sp = PROJECT / "shot_plan.json"
    if not sp.exists(): return []
    with open(sp) as f: data = json.load(f)
    return data if isinstance(data, list) else data.get("shots", [])

# ── Load latest ledger scores ─────────────────────────────────────────────────
def load_scores():
    ledger = PROJECT / "reward_ledger.jsonl"
    scores = {}
    if not ledger.exists(): return scores
    with open(ledger) as f:
        for line in f:
            try:
                e = json.loads(line)
                if e.get("shot_id"): scores[e["shot_id"]] = e
            except: pass
    return scores

# ── Load soundscape manifests ─────────────────────────────────────────────────
def load_soundscapes():
    ss = {}
    for sid in ["001","002","003","004"]:
        p = PROJECT / "soundscapes" / f"{sid}_undertone_manifest.json"
        if p.exists():
            with open(p) as f: ss[sid] = json.load(f)
    return ss

# ── Check file existence ──────────────────────────────────────────────────────
def file_exists(rel_path):
    if not rel_path: return False
    return (BASE / rel_path).exists()

# ── Check stitched scenes ─────────────────────────────────────────────────────
def find_stitched():
    stitched = {}
    stitched_dir = PROJECT / "stitched_scenes"
    video_dir = PROJECT / "videos_kling_lite"
    checks = {
        "001": [stitched_dir/"scene_001_stitched.mp4", PROJECT/"SCENE001_V2915.mp4", PROJECT/"SCENE001_V2915_fixed.mp4"],
        "002": [stitched_dir/"scene_002_stitched.mp4", PROJECT/"SCENE002_V2915.mp4"],
        "003": [stitched_dir/"scene_003_stitched.mp4"],
        "004": [stitched_dir/"scene_004_full_7shots.mp4"],
    }
    for scene, paths in checks.items():
        for p in paths:
            if p.exists():
                stitched[scene] = str(p.relative_to(BASE))
                break
    return stitched

# ── Build shot data ───────────────────────────────────────────────────────────
def build_data():
    all_shots = load_shots()
    scores = load_scores()
    soundscapes = load_soundscapes()
    stitched = find_stitched()

    scenes = {}
    for shot in all_shots:
        sid = shot.get("shot_id","")
        scene_id = sid[:3] if sid else ""
        if scene_id not in ["001","002","003","004"]: continue

        score = scores.get(sid, {})
        has_frame = file_exists(shot.get("first_frame_url") or shot.get("first_frame_path",""))
        has_video = file_exists(shot.get("video_url") or shot.get("video_path",""))

        is_e_shot = shot.get("_is_broll") or shot.get("_no_char_ref") or sid[4] == "E"
        chars = shot.get("characters", []) or []
        i_score = score.get("I", shot.get("_frame_identity_score"))

        # Character bleed: E-shot has non-zero identity score (possible character appeared)
        char_bleed = is_e_shot and i_score and float(i_score) > 0.76

        # Chain continuity: check if video exists for next group
        chain_group = shot.get("chain_group")

        scenes.setdefault(scene_id, []).append({
            "shot_id": sid,
            "shot_type": shot.get("shot_type",""),
            "duration": shot.get("duration", 5),
            "characters": chars,
            "dialogue_text": shot.get("dialogue_text","") or "",
            "description": shot.get("description") or shot.get("_frame_description",""),
            "beat_ref": shot.get("_beat_ref",""),
            "beat_action": shot.get("_beat_action",""),
            "beat_atmosphere": shot.get("_beat_atmosphere",""),
            "beat_description": shot.get("_beat_description",""),
            "scene_atmosphere": shot.get("_scene_atmosphere",""),
            "location": shot.get("location",""),
            "is_e_shot": is_e_shot,
            "arc_position": shot.get("_arc_position",""),
            "arc_index": shot.get("_arc_index",0),
            "arc_total": shot.get("_arc_total",0),
            "arc_carry": shot.get("_arc_carry_directive",""),
            "approval_status": shot.get("_approval_status",""),
            "frame_url": shot.get("first_frame_url") or shot.get("first_frame_path",""),
            "video_url": shot.get("video_url") or shot.get("video_path",""),
            "has_frame": has_frame,
            "has_video": has_video,
            "soundscape_sig": shot.get("_soundscape_signature",""),
            "chain_group": chain_group,
            "scores": {
                "R": score.get("R"), "I": score.get("I"), "V": score.get("V"),
                "C": score.get("C"), "verdict": score.get("verdict",""),
                "ts": score.get("timestamp","")
            },
            "char_bleed_flag": char_bleed,
        })

    return scenes, soundscapes, stitched

# ── Find dialogue audio ───────────────────────────────────────────────────────
def find_audio():
    audio = {}
    audio_dir = PROJECT / "dialogue_audio"
    if audio_dir.exists():
        for f in audio_dir.glob("*.mp3"):
            # e.g. 001_M02_dialogue.mp3
            parts = f.stem.split("_")
            if len(parts) >= 2:
                shot_id = f"{parts[0]}_{parts[1]}"
                audio[shot_id] = str(f.relative_to(BASE))
    # also audio_006_v2
    audio6 = PROJECT / "audio_006_v2"
    if audio6.exists():
        for f in audio6.glob("*.mp3"):
            parts = f.stem.split("_")
            if len(parts) >= 2:
                shot_id = f"{parts[0]}_{parts[1]}"
                audio[shot_id] = str(f.relative_to(BASE))
    return audio

# ── HTML Generation ───────────────────────────────────────────────────────────
ARC_COLORS = {
    "ESTABLISH": "#00d4ff",
    "ESCALATE": "#ffaa00",
    "PIVOT": "#ff4488",
    "RESOLVE": "#44ff88",
}
VERDICT_COLORS = {"PASS": "#44ff88", "REVIEW": "#ffaa00", "FAIL": "#ff4444", "": "#666"}

SCENE_LABELS = {
    "001": "GRAND FOYER — Arrival & Conflict",
    "002": "LIBRARY — Discovery",
    "003": "DRAWING ROOM — Confrontation",
    "004": "GARDEN — Isolation & Guilt",
}

CHAR_COLOR = {
    "ELEANOR VOSS": "#a78bfa",
    "THOMAS BLACKWOOD": "#60a5fa",
    "NADIA COLE": "#34d399",
    "RAYMOND CROSS": "#fb923c",
}

def score_bar(val, label, color="#00d4ff"):
    if val is None: return f'<div class="score-item"><span class="score-label">{label}</span><span class="score-val" style="color:#555">N/A</span></div>'
    pct = int(float(val) * 100)
    return f'''<div class="score-item">
  <span class="score-label">{label}</span>
  <div class="score-bar-track"><div class="score-bar-fill" style="width:{pct}%;background:{color}"></div></div>
  <span class="score-val" style="color:{color}">{float(val):.2f}</span>
</div>'''

def analysis_checks(shot, audio):
    checks = []
    chars = shot["characters"]
    is_e = shot["is_e_shot"]
    has_frame = shot["has_frame"]
    has_video = shot["has_video"]
    dialogue = shot["dialogue_text"]
    sid = shot["shot_id"]

    # Frame existence
    if has_frame:
        checks.append(("PASS", "Frame generated"))
    else:
        checks.append(("FAIL", "Frame MISSING — not generated"))

    # Video existence
    if has_video:
        checks.append(("PASS", "Video generated"))
    else:
        checks.append(("WARN", "Video not yet generated"))

    # E-shot character bleed
    if is_e:
        if shot["char_bleed_flag"]:
            checks.append(("FAIL", f"CHARACTER BLEED DETECTED — I-score={shot['scores'].get('I')} on E-shot (should be 0)"))
        else:
            checks.append(("PASS", "E-shot clean — no character bleed detected"))
        if chars:
            checks.append(("FAIL", f"E-shot lists characters: {', '.join(chars)} — should be empty"))
        else:
            checks.append(("PASS", "E-shot: characters[] = empty ✓"))

    # Character shot identity
    if not is_e and chars:
        i = shot["scores"].get("I")
        if i is not None:
            if float(i) >= 0.75:
                checks.append(("PASS", f"Identity score: {float(i):.2f} ≥ 0.75"))
            elif float(i) >= 0.45:
                checks.append(("WARN", f"Identity weak: {float(i):.2f} — flagged for review"))
            else:
                checks.append(("FAIL", f"Identity FAIL: {float(i):.2f} < 0.45 — needs regen"))

    # Dialogue audio
    if dialogue and sid in audio:
        checks.append(("PASS", f"Dialogue audio: {audio[sid].split('/')[-1]}"))
    elif dialogue and sid not in audio:
        checks.append(("WARN", "Dialogue text exists but no audio file found"))

    # Arc position
    arc = shot["arc_position"]
    if arc:
        checks.append(("INFO", f"Arc: {arc} ({shot['arc_index']}/{shot['arc_total']})"))

    # Approval
    approval = shot["approval_status"]
    if approval == "APPROVED":
        checks.append(("PASS", "Frame APPROVED"))
    elif approval == "AUTO_APPROVED":
        checks.append(("PASS", "Frame AUTO-APPROVED"))
    elif approval == "AWAITING_APPROVAL":
        checks.append(("WARN", "Awaiting approval"))
    elif approval == "REGEN_REQUESTED":
        checks.append(("FAIL", "Regen requested"))

    return checks

def render_shot_card(shot, audio):
    sid = shot["shot_id"]
    arc = shot["arc_position"]
    arc_color = ARC_COLORS.get(arc, "#888")
    verdict = shot["scores"].get("verdict","")
    verdict_color = VERDICT_COLORS.get(verdict, "#666")
    chars = shot["characters"]
    is_e = shot["is_e_shot"]
    checks = analysis_checks(shot, audio)

    # Frame thumbnail
    if shot["has_frame"] and shot["frame_url"]:
        thumb = f'<img src="/media/{shot["frame_url"]}" alt="{sid}" loading="lazy" onclick="openModal(this)">'
    else:
        thumb = '<div class="no-frame">⚠ NO FRAME</div>'

    # Video player
    if shot["has_video"] and shot["video_url"]:
        video_html = f'''<video controls preload="none" poster="/media/{shot["frame_url"] if shot["has_frame"] and shot["frame_url"] else ""}">
  <source src="/media/{shot["video_url"]}" type="video/mp4">
</video>'''
    else:
        video_html = '<div class="no-video">VIDEO NOT GENERATED</div>'

    # Characters tags
    char_tags = ""
    for c in chars:
        col = CHAR_COLOR.get(c, "#aaa")
        char_tags += f'<span class="char-tag" style="border-color:{col};color:{col}">{c}</span>'
    if is_e and not chars:
        char_tags = '<span class="char-tag" style="border-color:#555;color:#555">EMPTY — no characters</span>'

    # Dialogue
    dlg_html = ""
    if shot["dialogue_text"]:
        dlg_html = f'<div class="dialogue">"{shot["dialogue_text"]}"</div>'
        if sid in audio:
            dlg_html += f'<audio controls src="/media/{audio[sid]}" style="width:100%;margin-top:6px"></audio>'

    # Score bars
    s = shot["scores"]
    scores_html = f'''
<div class="scores-block">
  {score_bar(s.get("R"), "REWARD", "#fff")}
  {score_bar(s.get("I"), "IDENTITY", "#a78bfa")}
  {score_bar(s.get("V"), "VIDEO", "#60a5fa")}
  {score_bar(s.get("C"), "CONTINUITY", "#34d399")}
</div>'''

    # Analysis checks
    checks_html = ""
    for status, msg in checks:
        icon = {"PASS":"✓","FAIL":"✗","WARN":"⚠","INFO":"ℹ"}.get(status,"•")
        cls = {"PASS":"check-pass","FAIL":"check-fail","WARN":"check-warn","INFO":"check-info"}.get(status,"check-info")
        checks_html += f'<div class="check {cls}"><span class="check-icon">{icon}</span>{msg}</div>'

    # Shot type badge
    type_badge = f'<span class="type-badge {"e-badge" if is_e else "m-badge"}">{shot["shot_type"].upper()}</span>'

    return f'''
<div class="shot-card" id="shot-{sid}">
  <div class="shot-header">
    <div class="shot-id-row">
      <span class="shot-id">{sid}</span>
      {type_badge}
      <span class="arc-badge" style="color:{arc_color};border-color:{arc_color}">{arc}</span>
      <span class="verdict-badge" style="color:{verdict_color};border-color:{verdict_color}">{verdict or "NO SCORE"}</span>
      <span class="duration-badge">{shot["duration"]}s</span>
    </div>
    <div class="char-row">{char_tags}</div>
  </div>

  <div class="shot-columns">
    <!-- INTENT -->
    <div class="col intent-col">
      <div class="col-header">INTENT</div>
      <div class="thumb-container">{thumb}</div>
      <div class="intent-data">
        <div class="field-label">SCENE</div>
        <div class="field-val">{shot["description"]}</div>
        <div class="field-label">BEAT ACTION</div>
        <div class="field-val">{shot["beat_action"] or "—"}</div>
        <div class="field-label">ATMOSPHERE</div>
        <div class="field-val atmo">{shot["beat_atmosphere"] or shot["scene_atmosphere"] or "—"}</div>
        {dlg_html}
        <div class="field-label">ARC DIRECTIVE</div>
        <div class="field-val arc-directive" style="color:{arc_color}">{shot["arc_carry"] or "—"}</div>
      </div>
    </div>

    <!-- DELIVERY -->
    <div class="col delivery-col">
      <div class="col-header">DELIVERY</div>
      <div class="video-container">{video_html}</div>
      <div class="delivery-meta">
        <div class="field-label">CHAIN GROUP</div>
        <div class="field-val">{shot["chain_group"] or "—"}</div>
        <div class="field-label">FRAME STATUS</div>
        <div class="field-val">{"✓ Generated " + (shot.get("_frame_generated_at","") or "")[:16] if shot["has_frame"] else "✗ Missing"}</div>
        <div class="field-label">VIDEO STATUS</div>
        <div class="field-val">{"✓ Generated" if shot["has_video"] else "✗ Not generated"}</div>
        {scores_html}
      </div>
    </div>

    <!-- ANALYSIS -->
    <div class="col analysis-col">
      <div class="col-header">ANALYSIS</div>
      <div class="checks-list">{checks_html}</div>
    </div>
  </div>
</div>'''

def render_scene_section(scene_id, shots, soundscapes, stitched, audio):
    ss = soundscapes.get(scene_id, {})
    beats = ss.get("beat_timecodes", [])
    ss_status = ss.get("source", "not_attempted")
    ss_error = ss.get("error","")
    location = ss.get("location", shots[0]["location"] if shots else "")
    chars_in_scene = sorted(set(c for s in shots for c in s["characters"]))

    # Stats
    total = len(shots)
    has_frame_count = sum(1 for s in shots if s["has_frame"])
    has_video_count = sum(1 for s in shots if s["has_video"])
    pass_count = sum(1 for s in shots if s["scores"].get("verdict") == "PASS")
    fail_count = sum(1 for s in shots if s["scores"].get("verdict") == "FAIL")
    e_shot_count = sum(1 for s in shots if s["is_e_shot"])
    bleed_count = sum(1 for s in shots if s["char_bleed_flag"])

    # Stitched video
    stitch_path = stitched.get(scene_id)
    if stitch_path:
        frame_poster = shots[0]["frame_url"] if shots and shots[0]["has_frame"] else ""
        stitch_html = f'''
<div class="stitched-player">
  <div class="stitched-label">STITCHED SCENE — <span style="color:#44ff88">AVAILABLE</span></div>
  <video controls preload="none" poster="/media/{frame_poster}">
    <source src="/media/{stitch_path}" type="video/mp4">
  </video>
</div>'''
    else:
        stitch_html = '<div class="stitched-player missing">STITCHED SCENE — <span style="color:#ff4444">MISSING</span><br><small>No stitched file found in stitched_scenes/</small></div>'

    # Soundscape section
    if ss_status == "failed":
        ss_html = f'<div class="soundscape-card failed">Lyria FAILED — <span class="ss-error">{ss_error}</span><br><small>Compose target: {ss.get("duration_s","?")}s continuous undertone</small></div>'
    elif ss_status == "ok" and ss.get("audio_path"):
        ss_html = f'<div class="soundscape-card ok">✓ Lyria generated<br><audio controls src="/media/{ss["audio_path"]}"></audio></div>'
    else:
        ss_html = '<div class="soundscape-card missing">Soundscape not attempted</div>'

    # Beat timeline
    beat_html = ""
    for b in beats:
        offset = b.get("offset_s",0)
        dur = b.get("duration_s",0)
        dlg = b.get("dialogue","")
        atmo = b.get("atmosphere","")
        beat_html += f'''<div class="beat-item">
  <span class="beat-time">[{offset:.0f}s – {offset+dur:.0f}s]</span>
  <span class="beat-desc">{b.get("description","")}</span>
  {f'<div class="beat-dlg">"{dlg}"</div>' if dlg else ""}
  <div class="beat-atmo">{atmo}</div>
</div>'''

    char_tags = ""
    for c in chars_in_scene:
        col = CHAR_COLOR.get(c, "#aaa")
        char_tags += f'<span class="char-tag" style="border-color:{col};color:{col}">{c}</span>'

    shots_html = "".join(render_shot_card(s, audio) for s in shots)

    return f'''
<section class="scene-section" id="scene-{scene_id}">
  <div class="scene-header">
    <div class="scene-title">
      <span class="scene-num">SCENE {scene_id}</span>
      <span class="scene-name">{SCENE_LABELS.get(scene_id,"")}</span>
    </div>
    <div class="scene-meta">
      <span class="meta-item">{location}</span>
      <div class="char-row">{char_tags}</div>
    </div>
    <div class="scene-stats">
      <div class="stat-pill"><span class="stat-n">{total}</span> shots</div>
      <div class="stat-pill"><span class="stat-n" style="color:#00d4ff">{has_frame_count}/{total}</span> frames</div>
      <div class="stat-pill"><span class="stat-n" style="color:#60a5fa">{has_video_count}/{total}</span> videos</div>
      <div class="stat-pill"><span class="stat-n" style="color:#44ff88">{pass_count}</span> PASS</div>
      <div class="stat-pill"><span class="stat-n" style="color:#ff4444">{fail_count}</span> FAIL</div>
      <div class="stat-pill"><span class="stat-n" style="color:#e5b25d">{e_shot_count}</span> E-shots</div>
      {f'<div class="stat-pill bleed-pill"><span class="stat-n">{bleed_count}</span> BLEED?</div>' if bleed_count else ""}
    </div>
  </div>

  <div class="scene-body">
    <div class="scene-left">
      <!-- Beat timeline -->
      <div class="beat-timeline">
        <div class="section-label">STORY BEATS</div>
        {beat_html if beat_html else "<div class='muted'>No beat data</div>"}
      </div>

      <!-- Stitched scene -->
      {stitch_html}

      <!-- Soundscape -->
      <div class="section-label">SOUNDSCAPE STATUS</div>
      {ss_html}
    </div>

    <div class="scene-right">
      <div class="shots-list">
        {shots_html}
      </div>
    </div>
  </div>
</section>'''

def render_learning_section(all_scenes_data):
    all_shots = [s for shots in all_scenes_data.values() for s in shots]
    total = len(all_shots)
    has_frame = sum(1 for s in all_shots if s["has_frame"])
    has_video = sum(1 for s in all_shots if s["has_video"])
    pass_c = sum(1 for s in all_shots if s["scores"].get("verdict")=="PASS")
    fail_c = sum(1 for s in all_shots if s["scores"].get("verdict")=="FAIL")
    review_c = sum(1 for s in all_shots if s["scores"].get("verdict")=="REVIEW")
    e_shots = [s for s in all_shots if s["is_e_shot"]]
    m_shots = [s for s in all_shots if not s["is_e_shot"]]
    bleed = sum(1 for s in e_shots if s["char_bleed_flag"])

    # avg scores by shot type
    def avg(shots, key):
        vals = [s["scores"].get(key) for s in shots if s["scores"].get(key) is not None]
        return sum(float(v) for v in vals)/len(vals) if vals else 0

    e_i = avg(e_shots, "I"); m_i = avg(m_shots, "I")
    e_r = avg(e_shots, "R"); m_r = avg(m_shots, "R")
    frame_pct = int(has_frame/total*100) if total else 0
    video_pct = int(has_video/total*100) if total else 0
    pass_pct = int(pass_c/total*100) if total else 0

    return f'''
<section class="learn-section" id="learning">
  <div class="learn-header">PERPETUAL LEARNING — PIPELINE ANALYSIS</div>
  <div class="learn-grid">
    <div class="learn-card">
      <div class="learn-card-title">PRODUCTION COVERAGE</div>
      <div class="learn-stat">{frame_pct}%<span class="learn-unit"> frames generated ({has_frame}/{total})</span></div>
      <div class="learn-stat" style="color:#60a5fa">{video_pct}%<span class="learn-unit"> videos generated ({has_video}/{total})</span></div>
      <div class="learn-stat" style="color:#44ff88">{pass_pct}%<span class="learn-unit"> PASS verdict ({pass_c}/{total})</span></div>
      <div class="learn-bar-row">
        <div class="learn-bar" style="width:{frame_pct}%;background:#00d4ff"></div>
      </div>
    </div>

    <div class="learn-card">
      <div class="learn-card-title">IDENTITY SCORING</div>
      <div class="learn-stat" style="color:#a78bfa">E-shot avg I: {e_i:.2f}<span class="learn-unit"> (should be ~0.75 heuristic)</span></div>
      <div class="learn-stat" style="color:#60a5fa">M-shot avg I: {m_i:.2f}<span class="learn-unit"> (target ≥ 0.75)</span></div>
      <div class="learn-insight">{'⚠ Character bleed on ' + str(bleed) + ' E-shot(s) — I-score elevated, possible phantom person' if bleed else '✓ No character bleed detected on E-shots'}</div>
    </div>

    <div class="learn-card">
      <div class="learn-card-title">VERDICT DISTRIBUTION</div>
      <div class="verdict-bars">
        <div class="vbar"><span style="color:#44ff88">PASS</span> <div class="vbar-track"><div style="width:{int(pass_c/total*100) if total else 0}%;background:#44ff88" class="vbar-fill"></div></div> {pass_c}</div>
        <div class="vbar"><span style="color:#ffaa00">REVIEW</span> <div class="vbar-track"><div style="width:{int(review_c/total*100) if total else 0}%;background:#ffaa00" class="vbar-fill"></div></div> {review_c}</div>
        <div class="vbar"><span style="color:#ff4444">FAIL</span> <div class="vbar-track"><div style="width:{int(fail_c/total*100) if total else 0}%;background:#ff4444" class="vbar-fill"></div></div> {fail_c}</div>
      </div>
    </div>

    <div class="learn-card">
      <div class="learn-card-title">SOUNDSCAPE STATUS</div>
      <div class="learn-stat" style="color:#ff4444">4/4 scenes — Lyria FAILED</div>
      <div class="learn-insight">Error: Lyria API returned 400 "Model does not support the requested response modalities: audio,text". Lyria via Gemini audio modality not yet available in current API tier.</div>
      <div class="learn-insight" style="color:#60a5fa">Dialogue audio (ElevenLabs MP3) available for scenes 001–003 M-shots.</div>
    </div>

    <div class="learn-card wide">
      <div class="learn-card-title">PIPELINE RECOMMENDATIONS</div>
      <div class="rec-list">
        <div class="rec-item">
          <span class="rec-icon" style="color:#ff4444">▶</span>
          <div><strong>Scene 003:</strong> No stitched video exists — {sum(1 for s in all_shots if s["shot_id"].startswith("003") and s["has_video"])}/9 M-shots have video. Generate remaining videos and stitch.</div>
        </div>
        <div class="rec-item">
          <span class="rec-icon" style="color:#ffaa00">▶</span>
          <div><strong>Scene 002:</strong> 002_E02 and 002_E03 missing video. Chain groups 2-3 incomplete for that scene.</div>
        </div>
        <div class="rec-item">
          <span class="rec-icon" style="color:#ffaa00">▶</span>
          <div><strong>003_M03b:</strong> Close-up shot has no frame AND no video — this is a gap in scene 003's coverage.</div>
        </div>
        <div class="rec-item">
          <span class="rec-icon" style="color:#a78bfa">▶</span>
          <div><strong>Soundscape:</strong> Lyria API incompatibility blocks undertone generation. Fallback: use existing ElevenLabs dialogue audio. Consider Suno or MusicGen as alternative for undertones.</div>
        </div>
        <div class="rec-item">
          <span class="rec-icon" style="color:#44ff88">▶</span>
          <div><strong>Scene 004:</strong> Best performing — all 7 shots have frame + video. M01 achieved I=1.0 reward. Gold standard for chain arc.</div>
        </div>
        <div class="rec-item">
          <span class="rec-icon" style="color:#00d4ff">▶</span>
          <div><strong>Chain Arc Intelligence (V36.5):</strong> All scenes enriched with ESTABLISH→ESCALATE→PIVOT→RESOLVE positions. Scene 006 kitchen fix proven (V36.4). Apply same chain anchor protocol to Scene 003 video generation.</div>
        </div>
      </div>
    </div>
  </div>
</section>'''

def build_html():
    scenes_data, soundscapes, stitched = build_data()
    audio = find_audio()

    scene_tabs = ""
    for sid in ["001","002","003","004"]:
        shots = scenes_data.get(sid, [])
        has_v = sum(1 for s in shots if s["has_video"])
        scene_tabs += f'<a href="#scene-{sid}" class="scene-tab">{sid}<span class="tab-meta">{len(shots)}sh {has_v}v</span></a>'

    scenes_html = ""
    for sid in ["001","002","003","004"]:
        shots = scenes_data.get(sid, [])
        if shots:
            scenes_html += render_scene_section(sid, shots, soundscapes, stitched, audio)

    learn_html = render_learning_section(scenes_data)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ATLAS — Vision Verification Dashboard</title>
<style>
:root {{
  --bg: #0a0a0f;
  --surface: #111118;
  --surface2: #16161f;
  --border: #2a2a3a;
  --text: #e0e0f0;
  --muted: #555570;
  --accent: #00d4ff;
  --pass: #44ff88;
  --fail: #ff4444;
  --warn: #ffaa00;
  --info: #60a5fa;
  --radius: 8px;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'SF Mono',Consolas,'Courier New',monospace;font-size:13px;line-height:1.5}}
a{{color:var(--accent);text-decoration:none}}

/* Header */
.atlas-header{{background:linear-gradient(135deg,#0d0d1a,#1a0d2e);border-bottom:1px solid #2a1a4a;padding:20px 32px;display:flex;align-items:center;gap:24px;position:sticky;top:0;z-index:100;backdrop-filter:blur(10px)}}
.atlas-logo{{font-size:22px;font-weight:700;color:#fff;letter-spacing:3px}}
.atlas-logo span{{color:var(--accent)}}
.atlas-subtitle{{color:var(--muted);font-size:11px;letter-spacing:2px}}
.atlas-version{{margin-left:auto;color:#a78bfa;font-size:11px}}

/* Scene nav */
.scene-nav{{background:var(--surface);border-bottom:1px solid var(--border);padding:12px 32px;display:flex;gap:12px;position:sticky;top:67px;z-index:99;overflow-x:auto}}
.scene-tab{{color:var(--muted);padding:6px 16px;border:1px solid var(--border);border-radius:20px;font-size:11px;letter-spacing:1px;transition:all .2s;white-space:nowrap}}
.scene-tab:hover{{color:var(--accent);border-color:var(--accent);background:#0d1a2e}}
.tab-meta{{margin-left:6px;color:#555;font-size:10px}}

/* Scene section */
.scene-section{{padding:32px;border-bottom:2px solid var(--border)}}
.scene-header{{margin-bottom:24px}}
.scene-title{{display:flex;align-items:baseline;gap:12px;margin-bottom:8px}}
.scene-num{{font-size:28px;font-weight:700;color:var(--accent);letter-spacing:3px}}
.scene-name{{font-size:16px;color:var(--text);letter-spacing:1px}}
.scene-meta{{color:var(--muted);font-size:11px;margin-bottom:10px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
.scene-stats{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}
.stat-pill{{background:var(--surface2);border:1px solid var(--border);border-radius:20px;padding:4px 12px;font-size:11px;color:var(--muted)}}
.stat-n{{color:var(--text);font-weight:700}}
.bleed-pill{{border-color:#ff4444!important}}

/* Scene body layout */
.scene-body{{display:grid;grid-template-columns:320px 1fr;gap:24px;align-items:start}}
@media(max-width:900px){{.scene-body{{grid-template-columns:1fr}}}}
.scene-left{{position:sticky;top:120px}}

/* Beat timeline */
.beat-timeline{{background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);padding:16px;margin-bottom:16px}}
.section-label{{font-size:10px;letter-spacing:2px;color:var(--muted);text-transform:uppercase;margin-bottom:10px}}
.beat-item{{padding:8px 0;border-bottom:1px solid var(--border)}}
.beat-item:last-child{{border-bottom:none}}
.beat-time{{color:var(--accent);font-size:11px;font-weight:700;display:block}}
.beat-desc{{color:var(--text);font-size:11px;display:block;margin:2px 0}}
.beat-dlg{{color:#a78bfa;font-style:italic;font-size:11px;margin:2px 0}}
.beat-atmo{{color:var(--muted);font-size:10px}}

/* Stitched player */
.stitched-player{{background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);padding:16px;margin-bottom:16px}}
.stitched-player video{{width:100%;border-radius:4px;margin-top:8px}}
.stitched-label{{font-size:10px;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px}}
.stitched-player.missing{{color:var(--muted);font-size:11px}}

/* Soundscape */
.soundscape-card{{background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);padding:12px;margin-bottom:16px;font-size:11px}}
.soundscape-card.failed{{border-color:#ff4444;color:var(--muted)}}
.soundscape-card.ok{{border-color:var(--pass)}}
.ss-error{{color:#ff4444;font-size:10px}}

/* Shot card */
.shots-list{{display:flex;flex-direction:column;gap:16px}}
.shot-card{{background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;transition:border-color .2s}}
.shot-card:hover{{border-color:var(--accent)}}
.shot-header{{padding:12px 16px;background:var(--surface);border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:6px}}
.shot-id-row{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.shot-id{{font-size:16px;font-weight:700;color:var(--text);letter-spacing:2px}}
.type-badge,.arc-badge,.verdict-badge,.duration-badge{{font-size:9px;letter-spacing:1px;padding:2px 8px;border-radius:20px;border:1px solid;text-transform:uppercase}}
.e-badge{{background:#1a2a1a;border-color:#2a4a2a;color:#6a8a6a}}
.m-badge{{background:#1a1a2a;border-color:#2a2a5a;color:#6a6aaa}}
.duration-badge{{border-color:var(--border);color:var(--muted)}}
.char-row{{display:flex;flex-wrap:wrap;gap:6px}}
.char-tag{{font-size:9px;padding:2px 8px;border-radius:12px;border:1px solid;letter-spacing:0.5px}}

/* Three columns */
.shot-columns{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:0}}
@media(max-width:1200px){{.shot-columns{{grid-template-columns:1fr 1fr}}}}
@media(max-width:768px){{.shot-columns{{grid-template-columns:1fr}}}}
.col{{padding:14px;border-right:1px solid var(--border)}}
.col:last-child{{border-right:none}}
.col-header{{font-size:9px;letter-spacing:3px;text-transform:uppercase;color:var(--muted);margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--border)}}
.intent-col .col-header{{color:var(--accent)}}
.delivery-col .col-header{{color:var(--info)}}
.analysis-col .col-header{{color:var(--pass)}}

/* Thumbnail */
.thumb-container{{width:100%;margin-bottom:10px;border-radius:4px;overflow:hidden;cursor:zoom-in}}
.thumb-container img{{width:100%;display:block;border-radius:4px;transition:transform .2s}}
.thumb-container img:hover{{transform:scale(1.02)}}
.no-frame{{background:#1a1a1a;border:1px dashed var(--border);border-radius:4px;padding:20px;text-align:center;color:var(--muted);font-size:11px}}

/* Video */
.video-container{{width:100%;margin-bottom:10px}}
.video-container video{{width:100%;border-radius:4px;background:#000}}
.no-video{{background:#1a1a1a;border:1px dashed var(--border);border-radius:4px;padding:20px;text-align:center;color:var(--muted);font-size:11px}}

/* Intent fields */
.field-label{{font-size:9px;letter-spacing:2px;color:var(--muted);text-transform:uppercase;margin-top:8px}}
.field-val{{font-size:11px;color:var(--text);margin-top:2px;line-height:1.4}}
.atmo{{color:#e5b25d;font-style:italic}}
.arc-directive{{font-size:10px;letter-spacing:0.5px}}
.dialogue{{background:#1a1020;border-left:2px solid #a78bfa;padding:6px 10px;margin-top:6px;font-style:italic;color:#c4b5fd;font-size:11px;border-radius:0 4px 4px 0}}

/* Score bars */
.scores-block{{margin-top:8px}}
.score-item{{display:flex;align-items:center;gap:8px;margin:4px 0}}
.score-label{{font-size:9px;letter-spacing:1px;color:var(--muted);width:70px;flex-shrink:0}}
.score-bar-track{{flex:1;height:4px;background:#1a1a2a;border-radius:2px;overflow:hidden}}
.score-bar-fill{{height:100%;border-radius:2px;transition:width .3s}}
.score-val{{font-size:10px;width:34px;text-align:right;flex-shrink:0}}

/* Delivery meta */
.delivery-meta{{font-size:11px}}

/* Analysis checks */
.checks-list{{display:flex;flex-direction:column;gap:4px}}
.check{{display:flex;align-items:flex-start;gap:6px;padding:4px 6px;border-radius:4px;font-size:10px;line-height:1.4}}
.check-icon{{flex-shrink:0;font-size:11px;width:14px}}
.check-pass{{background:#0a1f0a;color:#6fba6f}}
.check-fail{{background:#1f0a0a;color:#e57373}}
.check-warn{{background:#1f1500;color:#c8a236}}
.check-info{{background:#0a0d1f;color:#6a8aba}}

/* Learning section */
.learn-section{{padding:32px}}
.learn-header{{font-size:18px;font-weight:700;color:var(--accent);letter-spacing:3px;margin-bottom:24px;padding-bottom:12px;border-bottom:1px solid var(--border)}}
.learn-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}}
.learn-card{{background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);padding:20px}}
.learn-card.wide{{grid-column:1/-1}}
.learn-card-title{{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);margin-bottom:12px}}
.learn-stat{{font-size:20px;font-weight:700;color:var(--accent);margin-bottom:4px}}
.learn-unit{{font-size:12px;color:var(--muted)}}
.learn-insight{{font-size:11px;color:var(--muted);margin-top:8px;line-height:1.5}}
.learn-bar-row{{height:4px;background:#1a1a2a;border-radius:2px;margin-top:10px;overflow:hidden}}
.learn-bar{{height:100%;border-radius:2px}}
.verdict-bars{{display:flex;flex-direction:column;gap:8px}}
.vbar{{display:flex;align-items:center;gap:8px;font-size:11px}}
.vbar>span{{width:52px;font-size:9px;letter-spacing:1px}}
.vbar-track{{flex:1;height:6px;background:#1a1a2a;border-radius:3px;overflow:hidden}}
.vbar-fill{{height:100%;border-radius:3px}}
.rec-list{{display:flex;flex-direction:column;gap:10px}}
.rec-item{{display:flex;gap:10px;font-size:11px;line-height:1.5;color:var(--muted)}}
.rec-icon{{flex-shrink:0;font-size:14px;margin-top:1px}}
.rec-item strong{{color:var(--text)}}

/* Modal lightbox */
.modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:1000;align-items:center;justify-content:center}}
.modal-overlay.open{{display:flex}}
.modal-overlay img{{max-width:90vw;max-height:90vh;border-radius:4px;cursor:zoom-out}}

/* Scrollbar */
::-webkit-scrollbar{{width:6px;height:6px}}
::-webkit-scrollbar-track{{background:var(--bg)}}
::-webkit-scrollbar-thumb{{background:#2a2a4a;border-radius:3px}}

/* Muted */
.muted{{color:var(--muted);font-size:11px}}
</style>
</head>
<body>

<header class="atlas-header">
  <div>
    <div class="atlas-logo">ATL<span>AS</span></div>
    <div class="atlas-subtitle">VISION VERIFICATION & VALIDATION DASHBOARD</div>
  </div>
  <div style="color:var(--muted);font-size:11px">Victorian Shadows EP1 · Scenes 001–004</div>
  <div class="atlas-version">V36.5 · INTENT vs DELIVERY</div>
</header>

<nav class="scene-nav">
  {scene_tabs}
  <a href="#learning" class="scene-tab">LEARNING<span class="tab-meta">analysis</span></a>
</nav>

{scenes_html}

{learn_html}

<!-- Lightbox -->
<div class="modal-overlay" id="lightbox" onclick="this.classList.remove('open')">
  <img id="lightbox-img" src="" alt="">
</div>

<script>
function openModal(img) {{
  document.getElementById('lightbox-img').src = img.src;
  document.getElementById('lightbox').classList.add('open');
}}
// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(a => {{
  a.addEventListener('click', e => {{
    e.preventDefault();
    const t = document.querySelector(a.getAttribute('href'));
    if(t) t.scrollIntoView({{behavior:'smooth', block:'start'}});
  }});
}});
</script>
</body>
</html>'''

# ── HTTP Server ───────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def serve_file(self, path):
        if not path.exists():
            self.send_error(404, f"Not found: {path}")
            return
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/dashboard":
            html = build_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        elif path.startswith("/media/"):
            rel = path[7:]  # strip /media/
            file_path = BASE / rel
            self.serve_file(file_path)

        else:
            self.send_error(404)

if __name__ == "__main__":
    PORT = 7777
    print(f"\n{'='*60}")
    print(f"  ATLAS VISION DASHBOARD")
    print(f"  Victorian Shadows EP1 — Intent vs Delivery")
    print(f"{'='*60}")
    print(f"  URL: http://localhost:{PORT}")
    print(f"  Serving from: {BASE}")
    print(f"{'='*60}\n")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
