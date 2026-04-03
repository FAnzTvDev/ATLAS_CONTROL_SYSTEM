================================================================================
V26 LIVE RENDER PATH ANALYSIS — START HERE
================================================================================

You have 4 documents that trace the EXACT code path from HTTP request to 
frame output. Start with this guide to navigate them.

================================================================================
QUICK NAVIGATION
================================================================================

GOAL: Understand what happens when a shot renders
  → Read: V26_EXECUTION_SUMMARY.txt (5 min)

GOAL: Find exact code locations of problems
  → Read: BREAKPOINT_LOCATIONS.md (15 min, with line numbers)

GOAL: Deep technical understanding
  → Read: RENDER_FLOW_TRACE_V26.md (45 min, complete trace)

GOAL: Index and reference
  → Read: V26_TRACE_INDEX.md (overview + quick lookup table)

================================================================================
THE 7 MISSING SELECTION POINTS (SUMMARY)
================================================================================

Your V26 controller MAKES decisions but DOESN'T SHOW them to the user:

1. Reframe Strategy Selection
   - Generates 5 strategies (continuity_match, emotional_push, etc.)
   - Takes the first (highest scored)
   - User never sees the other 4 options
   - Code: atlas_v26_controller.py:1305 → candidates[0]

2. Editorial Reuse Decisions
   - Algorithm decides which shots are "reuses"
   - Silently marks decision.action = "reuse"
   - User doesn't know until checking ledger
   - Code: atlas_v26_controller.py:1169

3. Multi-Angle Variants
   - Should generate 3 angles (wide, medium, close)
   - Actually generates 1 frame only
   - Zero variants exist for selection
   - Code: atlas_v26_controller.py:1543 → num_outputs=1

4. Identity Score Feedback
   - Scores generated frames (LOA ArcFace/DINOv2)
   - If score < 0.7, should regenerate
   - Actually: logs score, accepts frame
   - Code: atlas_v26_controller.py:1686

5. Prompt Lock Enforcement
   - Controller locks prompts (_prompt_locked=true)
   - Orchestrator should skip re-enrichment
   - Actually: Prompt Authority Gate overwrites anyway
   - Code: orchestrator_server.py:22083 (no lock check)

6. Doctrine Double-Check
   - Controller checks doctrine, clears scene
   - Orchestrator creates NEW doctrine runner, checks AGAIN
   - Different instances could give different results
   - Code: orchestrator_server.py:22133

7. End-Frame Approval
   - After video generation, end-frame becomes next shot's anchor
   - Should verify quality before chaining
   - Actually: Used immediately, errors cascade
   - Code: (in continuity_memory.py, not shown in this trace)

================================================================================
THE STRAIGHT-LINE PIPELINE (9 STEPS)
================================================================================

1. User clicks "Generate Shot"
        ↓
2. POST /api/v26/prepare → Controller.prepare_and_lock_scene()
        ↓
3. Controller checks: cast, doctrine, coverage, refs
   (HALTS if any fails)
        ↓
4. Controller.persist_locked_plan() → writes _prompt_locked=true
        ↓
5. POST /api/v26/generate-shot → retrieves locked plan
        ↓
6. Calls POST /api/auto/generate-first-frames-turbo (with governance header)
        ↓
7. Orchestrator runs: Prompt Authority Gate (AGAIN), doctrine checks (AGAIN)
   Builds generation tasks (1 frame per shot)
        ↓
8. ThreadPoolExecutor calls FAL parallel (10-15 workers)
   For each shot:
     - Get nano_prompt
     - Get refs
     - Call fal_run_with_key_rotation()
     - Download frame
     - Save to disk
        ↓
9. Return to UI with frame paths
   Done. No variants, no user selections, no rejections.

Result: Frame delivered in ~8 min for 151 shots. Fast but blind.

================================================================================
COMPARING WHAT SHOULD HAPPEN VS WHAT HAPPENS
================================================================================

REFRAME CANDIDATES:
  Should:  Generate 5 → Score → Show UI → Wait for user → Use selected
  Actually: Generate 5 → Take [0] → Continue

MULTI-ANGLE VARIANTS:
  Should:  Generate frame → Call multi_angle() → Get 3 variants → 
           Score with DINO → Show UI → Wait → Use selected
  Actually: Generate frame → Done

EDITORIAL REUSE:
  Should:  Identify pairs → Show source/target → Get approval → Reuse
  Actually: Silently decision.action = "reuse"

IDENTITY SCORES:
  Should:  Score frame → If <0.7: regenerate → Re-score → Approve/reject
  Actually: Score → Log → Accept

PROMPT LOCK:
  Should:  Lock in controller → Check lock in orchestrator → Skip re-write
  Actually: Lock in controller → Overwrite in orchestrator

DOCTRINE:
  Should:  Check in controller → Check in orchestrator (cache result) → Trust
  Actually: Check in controller → Check AGAIN in orchestrator (new instance)

END-FRAME:
  Should:  Generate video → Analyze end-frame → Approve → Use as anchor
  Actually: Generate video → Use end-frame immediately

================================================================================
WHICH DOCUMENT ANSWERS WHAT QUESTION
================================================================================

"How does the render actually work?"
  → V26_EXECUTION_SUMMARY.txt (overview)
  → RENDER_FLOW_TRACE_V26.md (complete details)

"Where exactly is the code I need to fix?"
  → BREAKPOINT_LOCATIONS.md (line numbers + code snippets)

"Why only 1 frame instead of 3 variants?"
  → BREAKPOINT_LOCATIONS.md § BREAKPOINT 3
  → RENDER_FLOW_TRACE_V26.md § PHASE 4

"Why don't users see editorial reuse decisions?"
  → BREAKPOINT_LOCATIONS.md § BREAKPOINT 2
  → RENDER_FLOW_TRACE_V26.md § PHASE 3.2

"How do I add an approval gate?"
  → BREAKPOINT_LOCATIONS.md (see "What Should Happen" section)
  → V26_TRACE_INDEX.md (copy the template pattern)

"What's the priority order for fixing things?"
  → V26_TRACE_INDEX.md § Implementation Priority

================================================================================
FILE SIZES AND READ TIME
================================================================================

V26_EXECUTION_SUMMARY.txt (13 KB) — 5 min read
  Quick overview. Start here.

BREAKPOINT_LOCATIONS.md (15 KB) — 15 min read
  Exact code locations. Use for implementation.

RENDER_FLOW_TRACE_V26.md (28 KB) — 45 min read
  Deep technical trace. Complete understanding.

V26_TRACE_INDEX.md (8 KB) — 5 min read
  Navigation guide and quick reference.

Total: 64 KB, ~70 minutes for complete understanding

================================================================================
THE CORE INSIGHT
================================================================================

V26 is OPTIMIZED FOR SPEED at the EXPENSE OF FEEDBACK.

It:
  ✓ Generates frames fast (parallel workers)
  ✓ Makes decisions automatically (doctrine, coverage, refs)
  ✓ Locks plans (persists to disk)
  ✗ Never asks user to approve decisions
  ✗ Never shows candidate options
  ✗ Never regenerates bad frames
  ✗ Never approves chain anchors
  ✗ Never rejects variants

The fix is to inject 7 approval gates that:
  1. Generate candidates
  2. Score them
  3. Return to UI with scores
  4. Wait for user selection
  5. Resume with user's choice

Same pattern for all 7 breakpoints.

================================================================================
NEXT STEPS
================================================================================

1. Read V26_EXECUTION_SUMMARY.txt (5 min)
2. Read BREAKPOINT_LOCATIONS.md (15 min)
3. Pick a breakpoint to fix (start with #3 — Multi-Angle)
4. Copy the "What Should Happen" pattern
5. Implement the approval gate pattern
6. Test with single shot
7. Repeat for remaining 6 breakpoints

Each breakpoint takes ~2 hours to implement properly.

Total effort: ~14 hours to add all 7 approval gates.
Result: System becomes interactive instead of blind.

================================================================================
DOCUMENTS IN THIS ANALYSIS
================================================================================

README_RENDER_TRACE.txt (this file)
  Navigation guide, summary, next steps

V26_EXECUTION_SUMMARY.txt
  5-minute high-level overview of the pipeline

BREAKPOINT_LOCATIONS.md
  7 missing selection points with exact line numbers and code

RENDER_FLOW_TRACE_V26.md
  Complete execution trace from HTTP request to disk output

V26_TRACE_INDEX.md
  Document index, quick reference table, testing verification

================================================================================

Start with: V26_EXECUTION_SUMMARY.txt
Questions? See: V26_TRACE_INDEX.md § Questions This Answers

