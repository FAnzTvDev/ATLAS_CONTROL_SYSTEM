# Scene 004 – First-Frame Autonomy Log

Date: 2025-10-30

This document captures the fixes and guardrails we added while stabilising Scene 004 so future phases can reuse the same playbook without regressions.

---

## What triggered the investigation

- Chen hair/brow drift kept returning even after good frames had been approved.
- Gallery UI cached stale stills and stitched videos reused previous-day clips.
- Fal video runs failed silently on duration mismatches, burning credits.
- Manual downloading was the only way to see every frame Fal produced.

## Key guardrails reinstated

1. **Three-frame QC loop**
   - Entrance, reaction, monitors are regenerated together.
   - Hard stop after three retries; failing runs flip to `needs_regen`.
   - Hair down, glasses on, clean brow, blocking, no subtitles tested automatically.

2. **Hero locks for stills and videos**
   - Approved Fal frames are copied to `hero_refs/<shot>_LOCK.jpg` / `.mp4`.
   - Gallery always references the hero file; re-generations cannot overwrite it without an explicit unlock.

3. **Fal asset fetch + cache busting**
   - Every successful LTX job is downloaded automatically and archived.
   - `/media/...` URLs now append `?t=<timestamp>` so the UI refreshes thumbnails immediately.

4. **Cost visibility + audit log**
   - Gallery header pulls `/api/gallery/costs` showing image/video spend and generation counts.
   - `scene004_costs.json` (generated after runs) records per-shot spend for audits.

5. **Verification snapshot**
   - `hero_refs/dashboard_snapshot_004.png` captures the gallery state pre-video-run.
   - Useful for investigations and for Atlas/ChatGPT autonomy review.

## Lessons learned

- Do not lock hero assets until QC confirms hair/glasses/brow, otherwise regression slips back in.
- Fal request IDs alone are not enough—the automation must download the MP4/JPG to disk and promote it before stitching.
- Duration guard (6/8/10 s only) must run before queuing LTX to avoid 422 errors.
- Live refresh in the gallery is essential; cached thumbnails hide regressions.

## Action items

- Integrate dashboard view inside the Atlas Render Gallery so operators see all Fal results without leaving the tool.
- Wire up automatic Fal downloads after every success and retire manual “Download” steps.
- Maintain this log for each scene; copy as a template for future autonomy phases.

