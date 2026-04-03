# Auto Studio Verification Workflow (Character & Wardrobe Focus)

## 1. Refresh Environment
1. Close the Auto Studio tab.
2. Run `scripts/refresh_auto_studio.sh` to restart the orchestrator and mount the new media paths.
3. Hard-refresh `http://localhost:9999/auto-studio`.

## 2. Cast & Wardrobe Lock
1. In the verification panel, regenerate each character reference until the wardrobe and hair match your intent.
2. Character images live in `pipeline_outputs/<project>/character_library_locked/`—the UI now serves these directly via `/project-media/...`.
3. Approve casting once every lead looks correct.

## 3. Location Masters
1. Use the location cards to regenerate or drop in your own plates under `pipeline_outputs/<project>/location_masters/`.
2. Hit the **⟳ Sync** button in the Realtime Generations panel to pull any external renders into the UI.

## 4. First Frames (Scene-by-Scene)
1. Click “Generate All Assets” only after casting/locations are locked.
2. Once character/location refs finish, click “Generate First Frames”.
3. The Live Generations strip shows each frame as it completes. Use **⟳ Sync** if you render shots manually via fal.ai.

## 5. Shots Review & Editing
1. Scroll to **Shots Review**. Use the Scene dropdown to focus on a single scene.
2. Each card includes:
   - Thumbnail (`first_frame_url`)
   - Nano prompt (image)
   - LTX motion prompt (video)
   - Duration, type, location fields
3. Fix wardrobe/hair by editing the nano prompt or regenerating the character reference; click “Regenerate” next to any shot to re-run just that frame.
4. Click “Preview” to compare the script beat to the current prompts.
5. Mark shots as ✅ when satisfied; use **Save All Edits** to persist prompt/duration changes.
6. Use **⟳ Reload Shots** to pull updated frames/prompts from disk without reloading the whole project.

## 6. Proceed to Video in Batches
1. Only approved shots are queued. Filter by scene and approve a handful at a time.
2. Click “Proceed to Video”; the renderer now consumes the corrected prompts and wardrobe references.
3. Watch the Live Generations panel for video progress; stop at any time via the STOP button in the Agent Workflow if you spot an issue.

## 7. Manual Imports
- Dropping external fal.ai outputs into `pipeline_outputs/<project>/first_frames/` or `.../character_library_locked/` + hitting **⟳ Sync** keeps Auto Studio “aware” of the new frames.
- The shot-plan API now resolves first-frame URLs from `first_frames`, `renders`, `videos`, and the global render gallery, so the UI stays in sync.
