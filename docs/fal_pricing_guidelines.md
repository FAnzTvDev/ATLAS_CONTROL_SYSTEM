# FAL Pricing Guidelines (Phase 8.7)

## Duration Tiers (ltxv2/image-to-video/fast)
| Clip Length | Typical FAL Charge* |
|-------------|---------------------|
| 6–8 s       | $0.80–$0.95         |
| 9–10 s      | $0.95–$1.10         |
| 12–15 s     | $1.15–$1.35         |

> *Assumes default quality and single render. Retries or higher-resolution modes add 15–25%.

## Per-Shot Budget Template
```
image_cost = $0.50   # nano-banana edit (3 candidates)
video_cost = $1.00   # average 9–10 s clip
per_shot   = image_cost + video_cost = $1.50
with 20% buffer: $1.80
```

## Scene/Season Forecast Examples
| Scope               | Shot Count | Base Spend | +15% Buffer | Recommended Credit |
|---------------------|------------|------------|-------------|--------------------|
| Dialogue scene      | 15         | $22.50     | +$3.40      | $26                |
| First live test     | 20         | $30.00     | +$4.50      | $35–$40            |
| Seven-episode run†  | 90         | $135.00    | +$20.00     | $170–$180          |

†Adjust linearly for longer seasons. A 45-minute episode (≈180 shots) doubles the budget; set `MAX_FAL_SPEND_USD` accordingly before executing the pipeline.

## Guardrail Environment Variables
```
MAX_FAL_SPEND_USD   # default 16.00
FAL_IMAGE_COST_USD  # default 0.75
FAL_VIDEO_COST_USD  # default 1.00
```

Control these to fit your plan tier. The spend guard writes to `config/fal_spend.json` and halts the run when the remaining budget is insufficient.


## Tooling
Run the pacing calculator to derive shot counts before setting the spend caps:
```bash
python3 scripts/pacing_cost_calculator.py 45 45m_prestige
```
Use `--scenes` or `--shots` to plug in exact schedule plans. Once you have the target shot count, set
`MAX_FAL_SPEND_USD` accordingly and rerun the rehearsal command with `--record-spend` to enforce the cap.
