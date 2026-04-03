#!/usr/bin/env python3
"""
ATLAS E-Shot Spatial Map + Fixer V31.0
Defines location-specific E01/E02/E03 content and patches shot_plan.json.

AUDIT FINDINGS:
  001_E01 ❌  ACTION= character beat, not exterior establishing
  001_E03 ❌  ACTION= character beat, not door-handle insert
  002_E01 ❌  ACTION= character beat, not library-wing exterior
  002_E03 ❌  ACTION= character beat, not book-spine insert
  003_E02 ⚠️  "The room breathes" — vague interior
  005_E02 ⚠️  "The room breathes" — vague interior
  006_E02 ⚠️  "The room breathes" — vague interior
  All others: correct or acceptable

ROOT CAUSE: prompt_finalizer_v31.py used _beat_action for ALL shots.
E-shots must use the spatial map, never the character beat action.
"""

import json
from pathlib import Path

SHOT_PLAN = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/pipeline_outputs/victorian_shadows_ep1/shot_plan.json")

REALISM_ANCHOR = "photorealistic film frame, 35mm Kodak 5219, practical lighting, no digital artifacts, film grain, natural skin texture"

# ─────────────────────────────────────────────────────────────────────────────
# SPATIAL MAP — for inject_tone_shots() to consult
# Key: canonical location name (uppercase, matches shot_plan location field)
# Each entry defines exactly what E01 / E02 / E03 should show.
#
# E01 = EXTERIOR ESTABLISHING: Where are we geographically? The "outside" view
#        that orients the audience before we enter the space.
# E02 = INTERIOR ATMOSPHERE: Empty room, no people. Shows the room's character
#        and spatial DNA — what the room IS before people fill it.
# E03 = DETAIL INSERT: One meaningful object in this room. The close-up that
#        earns meaning — what the room CONTAINS that the story cares about.
# ─────────────────────────────────────────────────────────────────────────────

SPATIAL_MAP = {

    "HARGROVE ESTATE - GRAND FOYER": {
        "E01": {
            "shot_type": "establishing",
            "description": "EXT. iron estate gates, morning mist, mansion beyond",
            "prompt": (
                "EXTERIOR ESTABLISHING. The iron entrance gates of Hargrove Estate at dawn. "
                "Rusted black ironwork, stone piers with weathered crests. "
                "Morning mist lies across the gravel drive beyond. "
                "The Victorian limestone mansion looms in middle distance, one window glowing faintly. "
                "Grey-blue sky, overgrown verge. The sleeping house. "
                "[CAMERA: 24mm, f/8, static wide, deep field] "
                "[PALETTE: cool grey morning, desaturated limestone, iron black, single amber window] "
                "[PHYSICS: pre-dawn diffused light, no direct sun, mist catching gate ironwork] "
                "[AESTHETIC: Victorian gothic realism, NO people, NO CGI] "
                "[FRAMING: full frame geography, gates foreground, mansion receding into mist]"
            ),
        },
        "E02": {
            "shot_type": "insert",
            "description": "INT. foyer — empty. Grand staircase, chandelier, dust sheets",
            "prompt": (
                "INTERIOR WIDE — EMPTY. Grand Victorian foyer. "
                "No people. "
                "Single curved cream marble staircase rises center-background, white balustrades, brass handrail. "
                "Crystal chandelier (unlit) suspended from double-height plasterwork ceiling. "
                "Dark mahogany-paneled walls with wainscoting. "
                "White dust sheets draped over console table and chairs — ghostly shapes. "
                "Persian carpet runner. Tall arched stained-glass windows frame-left, morning light fracturing into colored shards. "
                "Oil portrait of stern Victorian woman above staircase landing, watching. "
                "Dust motes visible in light shafts. Absolute stillness. "
                "[CAMERA: 28mm, f/5.6, eye-level static, full room depth] "
                "[PALETTE: muted grey-gold, stained-glass color shards on dark floor, cool shadow] "
                "[PHYSICS: stained glass side-lighting, no overhead illumination, atmospheric depth] "
                "[AESTHETIC: Victorian gothic realism, NO people, NO CGI] "
                "[FRAMING: full room geography, staircase dominant, chandelier in upper third]"
            ),
        },
        "E03": {
            "shot_type": "insert",
            "description": "INSERT — front door handle. Tarnished brass. A hand about to turn it.",
            "prompt": (
                "EXTREME CLOSE INSERT. The front door handle of Hargrove Estate. "
                "Tarnished brass, cold to touch, Victorian pattern worn smooth at the grip. "
                "A gloved hand reaches into frame from off-left, fingers closing around the handle — about to turn it. "
                "The first human contact with this sleeping house. "
                "Door painted black, iron keyhole plate below. Shallow depth of field. "
                "[CAMERA: 100mm macro, f/2.8, static] "
                "[PALETTE: dark brass, cold grey, single warm key light from outside] "
                "[PHYSICS: exterior daylight behind, threshold shadow on handle surface] "
                "[AESTHETIC: Victorian gothic realism, tactile metal surfaces, NO CGI] "
                "[FRAMING: handle fills 60% of frame, gloved hand entering from edge, keyhole visible]"
            ),
        },
    },

    "HARGROVE ESTATE - LIBRARY": {
        "E01": {
            "shot_type": "establishing",
            "description": "EXT. library wing windows, amber lamplight, Victorian stone facade",
            "prompt": (
                "EXTERIOR ESTABLISHING. The library wing of Hargrove Estate, morning. "
                "Two tall arched windows, stone-mullioned, warm amber lamplight glowing within against grey morning sky. "
                "Victorian limestone facade, ivy at the corners, leaded glass panes. "
                "Gravel path below windows. Overgrown hedge-line. Someone is inside among the books. "
                "[CAMERA: 24mm, f/8, static, slight low angle] "
                "[PALETTE: warm amber window glow against cool stone grey, morning blue-grey sky] "
                "[PHYSICS: interior lamp warmth leaking through glass, no direct sunlight, diffused exterior] "
                "[AESTHETIC: Victorian realism, NO people visible through glass, NO CGI] "
                "[FRAMING: two arched windows center-frame, stonework framing them, ivy detail frame-left]"
            ),
        },
        "E02": {
            "shot_type": "insert",
            "description": "INT. library — empty. Floor-to-ceiling shelves, rolling ladder, warm lamp",
            "prompt": (
                "INTERIOR WIDE — EMPTY. Victorian private library. "
                "No people. "
                "Floor-to-ceiling mahogany bookshelves on all walls, packed with leather-bound volumes. "
                "Rolling brass library ladder resting on upper rail at left. "
                "Central mahogany reading table, surface clear. "
                "Two leather wingback chairs, one slightly angled as if recently vacated. "
                "Tall arched windows admitting warm amber morning light slanting across leather spines. "
                "Standing globe beside table. Dust on every surface. "
                "Warm lamp glow pooling on the nearest shelves, deep shadows in alcoves. "
                "[CAMERA: 28mm, f/5.6, eye-level, slightly off-center] "
                "[PALETTE: warm amber, deep mahogany brown, dusty leather spine greens/reds, shadow-filled alcoves] "
                "[PHYSICS: single lamp warm key, window ambient fill, candlelit quality] "
                "[AESTHETIC: Victorian gentlemen's library, NO people, NO CGI] "
                "[FRAMING: shelves fill 3/4 of frame on both sides, reading table center, ladder frame-left]"
            ),
        },
        "E03": {
            "shot_type": "insert",
            "description": "INSERT — book spine, gold letters, folded letter tucked between volumes",
            "prompt": (
                "EXTREME CLOSE INSERT. A row of leather-bound book spines on a library shelf. "
                "Gold-embossed lettering catches warm lamplight — a title half-readable. "
                "Between two volumes, the cream-coloured edge of a folded letter protrudes — "
                "yellowed with age, tucked there deliberately or forgotten. "
                "The secret hidden in plain sight. "
                "Dust on the top edges of the spines. Shallow depth of field. "
                "[CAMERA: 100mm macro, f/2.8, static, slightly oblique angle] "
                "[PALETTE: warm amber lamp on leather, gold embossing highlights, cream paper against dark binding] "
                "[PHYSICS: warm side-lighting from reading lamp, edge-lit letter paper] "
                "[AESTHETIC: Victorian book detail, tactile leather and paper, NO CGI] "
                "[FRAMING: spines fill frame, letter edge visible between volumes, gold lettering catches light]"
            ),
        },
    },

    "HARGROVE ESTATE - DRAWING ROOM": {
        "E01": {
            "shot_type": "establishing",
            "description": "EXT. drawing room French doors, lamplight behind curtains, stone facade",
            "prompt": (
                "EXTERIOR ESTABLISHING. The drawing room wing of Hargrove Estate. "
                "French doors and tall windows, heavy drapes drawn but dim light behind them — someone is inside. "
                "Victorian stone facade, morning light. "
                "Formal garden terrace visible at the base of the French doors, flagstones frost-dusted. "
                "[CAMERA: 24mm, f/8, static, slight low angle] "
                "[PALETTE: cool morning grey, dim interior light through curtain gap, frost-white stone] "
                "[PHYSICS: overcast morning diffusion, no direct sun, interior lamp leaked through curtain gap] "
                "[AESTHETIC: Victorian gothic realism, NO people, NO CGI] "
                "[FRAMING: French doors center, terrace foreground, stone facade framing]"
            ),
        },
        "E02": {
            "shot_type": "insert",
            "description": "INT. drawing room — empty. White dust sheets, Steinway piano, silver candelabras",
            "prompt": (
                "INTERIOR WIDE — EMPTY. Victorian drawing room. "
                "No people. "
                "Furniture under white dust sheets — sculptural shapes in dim light. "
                "Grand Steinway piano frame-left, its fitted sheet grey with dust. "
                "Silver candelabras on the mantelpiece, unlit, tarnished. "
                "Crystal display cases along far wall, contents dim. "
                "Marble fireplace surround, cold grey ash. "
                "Sage green wallpaper visible above the wainscoting where dust sheets don't reach. "
                "Dim grey light through half-curtained windows. A room preserved in amber, waiting. "
                "[CAMERA: 28mm, f/5.6, static, slight low angle] "
                "[PALETTE: grey dust-sheet white, dim diffused grey, sage green wallpaper, silver tarnish] "
                "[PHYSICS: overcast window fill only, deep interior shadow, no lamp light] "
                "[AESTHETIC: Victorian gothic abandonment, NO people, NO CGI] "
                "[FRAMING: piano frame-left, dust-sheeted furniture filling room, fireplace background center]"
            ),
        },
        "E03": {
            "shot_type": "insert",
            "description": "INSERT — fireplace mantel. Tarnished candelabra, cold wax. Gloved hand.",
            "prompt": (
                "EXTREME CLOSE INSERT. A Victorian fireplace mantelpiece. "
                "White marble edge, cold. "
                "Tarnished silver candelabra, wax dripped in frozen rivulets. "
                "A gloved hand rests on the marble edge — still, waiting, claiming ownership. "
                "Dust on every surface. Cold ash in the grate below. "
                "[CAMERA: 100mm macro, f/2.8, static, eye-level on mantel surface] "
                "[PALETTE: marble white, silver tarnish grey, cold wax ivory, charcoal ash] "
                "[PHYSICS: dim window diffusion only, no warmth, cold and still] "
                "[AESTHETIC: Victorian interior detail, tactile cold marble and metal, NO CGI] "
                "[FRAMING: candelabra fills upper frame, gloved hand on marble edge lower-right, cold ash grate suggested below]"
            ),
        },
    },

    "HARGROVE ESTATE - GARDEN": {
        "E01": {
            "shot_type": "establishing",
            "description": "EXT. view through French doors from inside house — garden beyond, overgrown",
            "prompt": (
                "EXTERIOR ESTABLISHING — from inside looking out. "
                "French doors standing open or slightly ajar. "
                "Beyond: the Victorian walled garden. "
                "Dead roses on rusted iron trellises against grey stone wall. "
                "Dry stone fountain, basin empty and cracked, moss at base. "
                "Overgrown gravel paths disappearing into hedge. "
                "Rolling Yorkshire countryside glimpsed over the far wall. "
                "Grey overcast sky. The garden waits. "
                "[CAMERA: 24mm, f/5.6, looking outward through doors, doors as frame] "
                "[PALETTE: cool grey-green, dead-rose rust and brown, overcast sky, moss grey] "
                "[PHYSICS: overcast diffused exterior light, interior shadow framing the view] "
                "[AESTHETIC: Victorian overgrown garden, desolate beauty, NO people, NO CGI] "
                "[FRAMING: French door frame at edges, garden receding into distance, fountain center-background]"
            ),
        },
        "E02": {
            "shot_type": "insert",
            "description": "GARDEN interior — paths, trellises, dead roses, stone fountain",
            "prompt": (
                "INTERIOR OF GARDEN — EMPTY. The Victorian walled garden. "
                "No people. "
                "Gravel paths overtaken by moss and grass, converging toward dry fountain. "
                "Iron trellises heavy with dead rose canes, rust-brown. "
                "Cracked stone fountain, basin dry. Weathered teak bench beside it. "
                "Stone boundary wall, lichen-covered. "
                "Copper beeches visible over the far wall. "
                "Grey overcast sky above. Absolute desolation and neglected beauty. "
                "[CAMERA: 28mm, f/5.6, eye-level static, slight wind movement in dead canes] "
                "[PALETTE: dead rose rust, grey gravel, moss green, stone grey, overcast white sky] "
                "[PHYSICS: flat overcast diffusion, no direct sun, cold grey light on all surfaces] "
                "[AESTHETIC: overgrown Victorian garden, melancholy beauty, NO people, NO CGI] "
                "[FRAMING: paths lead eye to fountain, trellises frame left and right, open sky upper third]"
            ),
        },
        "E03": {
            "shot_type": "insert",
            "description": "INSERT — dead rose on trellis, or sundial, or gate latch",
            "prompt": (
                "EXTREME CLOSE INSERT. A dead rose on an iron garden trellis. "
                "Dried petals, rust brown, clinging to the hip. "
                "A single thorn catching grey light. "
                "Iron wire of the trellis behind it, rust-orange, flaking. "
                "Everything beautiful and past. Shallow depth of field. "
                "Alternative: a stone sundial, gnomon casting no shadow in the overcast. "
                "[CAMERA: 100mm macro, f/2.8, static, slight oblique] "
                "[PALETTE: dried rose brown, iron rust orange, grey thorn, cold diffused light] "
                "[PHYSICS: flat overcast, no shadow, delicate backlight on dried petal edge] "
                "[AESTHETIC: Victorian garden detail, memento mori, tactile dried organic, NO CGI] "
                "[FRAMING: rose fills 50% of frame, trellis iron behind soft, sky beyond pure grey-white]"
            ),
        },
    },

    "HARGROVE ESTATE - MASTER BEDROOM": {
        "E01": {
            "shot_type": "establishing",
            "description": "EXT. upper floor window, heavy curtain half-drawn, candlelight within",
            "prompt": (
                "EXTERIOR ESTABLISHING. An upper floor window of Hargrove Estate — the master bedroom. "
                "Tall sash window, leaded glass. Heavy velvet curtain half-drawn from inside. "
                "Candlelight flickering from within — warm amber against the grey exterior stone. "
                "Someone is in this room. The house is not entirely empty. "
                "Ivy at the stone surround. Morning light on the facade. "
                "[CAMERA: 24mm, f/8, slight upward angle from below] "
                "[PALETTE: cold grey limestone, warm amber candle through glass, ivy green-grey] "
                "[PHYSICS: morning diffused exterior, warm interior leak through half-curtain gap] "
                "[AESTHETIC: Victorian exterior, intimacy implied by candlelight, NO people visible, NO CGI] "
                "[FRAMING: window center-frame, curtain gap showing amber light, stone facade surrounding]"
            ),
        },
        "E02": {
            "shot_type": "insert",
            "description": "INT. bedroom — empty. Four-poster bed, vanity mirror, velvet curtains, photographs",
            "prompt": (
                "INTERIOR WIDE — EMPTY. Victorian master bedroom. "
                "No people. "
                "Carved mahogany four-poster bed, dusty canopy drawn, burgundy coverlet faded at the folds. "
                "Heavy velvet curtains half-drawn, morning light pressing through the gap. "
                "Marble-topped washstand, porcelain basin, silver-topped bottles tarnished. "
                "Vanity table with tarnished mirror — silver hairbrush, scattered toiletry set. "
                "On the bedside table: a small silver-framed portrait, face not yet visible. "
                "Persian rug, colors muted under dust. "
                "A room that held a life — preserved, not lived in. "
                "[CAMERA: 28mm, f/5.6, static, eye-level] "
                "[PALETTE: burgundy faded to dusty rose, dark mahogany, grey dust, morning window sidelight] "
                "[PHYSICS: curtain gap as key light, warm-cool mix of candle remnant and grey morning] "
                "[AESTHETIC: Victorian private interior, intimate stillness, NO people, NO CGI] "
                "[FRAMING: four-poster dominant center, vanity frame-right, window light frame-left, portrait on bedside visible]"
            ),
        },
        "E03": {
            "shot_type": "insert",
            "description": "INSERT — silver-framed portrait on bedside table. Harriet's face, half in shadow.",
            "prompt": (
                "EXTREME CLOSE INSERT. A small silver-framed portrait on the bedside table. "
                "The frame is tarnished, Victorian-era photograph inside. "
                "A woman's face — stern Victorian expression, dark formal dress, piercing eyes. "
                "Half the face in deep shadow, half caught in morning window light. "
                "The house's true occupant. She watches from the past. "
                "Dust on the frame's edge. Shallow depth of field. "
                "[CAMERA: 100mm macro, f/2.8, static, slight oblique looking down at table surface] "
                "[PALETTE: silver tarnish grey, sepia photograph tone, deep shadow half, morning light half] "
                "[PHYSICS: single window key light from side, deep cast shadow in portrait detail] "
                "[AESTHETIC: Victorian portrait photography, memento mori, NO CGI] "
                "[FRAMING: frame fills 60% of shot, woman's face center with half in shadow, bedside surface below]"
            ),
        },
    },

    "HARGROVE ESTATE - KITCHEN": {
        "E01": {
            "shot_type": "establishing",
            "description": "EXT. service entrance below stairs, copper window glow, coal scuttle",
            "prompt": (
                "EXTERIOR ESTABLISHING. The service entrance of Hargrove Estate — below-stairs access. "
                "Stone steps descending to a low door. "
                "Copper-warm light spilling from the kitchen window at pavement level. "
                "Coal scuttle beside the door, iron boot-scrape at the step. "
                "This is the working heart of the house — the one entrance that smells of something real. "
                "[CAMERA: 24mm, f/8, static, slightly low looking down at entrance level] "
                "[PALETTE: copper-warm window glow against cold stone grey, coal black scuttle] "
                "[PHYSICS: interior kitchen warmth leaking through small window, exterior cold diffusion] "
                "[AESTHETIC: Victorian below-stairs realism, working class warmth, NO people, NO CGI] "
                "[FRAMING: service door center, steps leading down, window glow lower-right, coal scuttle as detail]"
            ),
        },
        "E02": {
            "shot_type": "insert",
            "description": "INT. kitchen — empty. Cast-iron range warm, copper pots hanging, flagstone floor",
            "prompt": (
                "INTERIOR WIDE — EMPTY. Victorian estate kitchen. "
                "No people. "
                "Whitewashed brick walls, low timber-beamed ceiling with hanging copper pots — "
                "a dozen of them, different sizes, catching the firelight. "
                "Cast-iron range, firebox door slightly ajar, low orange glow within — still faintly warm. "
                "Flagstone floor worn smooth at range and sink. "
                "Pine work table, surface scarred from decades of preparation. "
                "Stone sink, cold tap. Bundles of dried herbs hanging from beam. "
                "The only room in the house where something still breathes. "
                "[CAMERA: 28mm, f/4, static, eye-level, slight warm-side tilt] "
                "[PALETTE: warm orange from range firebox, copper glow on hanging pots, cool stone grey floor, white-wash walls] "
                "[PHYSICS: single firebox warm key light, practical lantern overhead fill, long shadows across flagstones] "
                "[AESTHETIC: Victorian working kitchen, warmth and pragmatism, NO people, NO CGI] "
                "[FRAMING: range center-background glowing, copper pots hanging upper frame, flagstones leading in from foreground]"
            ),
        },
        "E03": {
            "shot_type": "insert",
            "description": "INSERT — copper pot on range, steam rising, reflection warped in curved surface",
            "prompt": (
                "EXTREME CLOSE INSERT. A copper pot resting on the cast-iron range. "
                "Surface polished to a deep warm glow, dented and well-used. "
                "Steam rising from the lid — thin, persistent. "
                "The curved surface reflects a warped mirror image of the kitchen: "
                "firelight, hanging pots, the room distorted in copper. "
                "Orange firebox glow below. The only thing in this house that is still alive. "
                "[CAMERA: 100mm macro, f/2.8, static, eye-level on pot] "
                "[PALETTE: deep copper warm, orange fire reflection, distorted kitchen in pot surface, steam white] "
                "[PHYSICS: direct firebox radiance on pot surface, backlit steam from above by lantern] "
                "[AESTHETIC: Victorian kitchen still-life, warmth and craft, NO CGI] "
                "[FRAMING: pot fills 70% of frame, steam rising through upper frame, curved reflection visible in pot surface]"
            ),
        },
    },

    "HARGROVE ESTATE - GRAND STAIRCASE": {
        "E01": {
            "shot_type": "establishing",
            "description": "EXT. view of staircase hall from bottom of stairs — domed skylight above",
            "prompt": (
                "INTERIOR ESTABLISHING — FROM STAIRCASE BASE. "
                "Looking up the Grand Staircase hall. "
                "Single curved marble staircase rising in a graceful sweep. "
                "Brass carpet-rod fasteners on each tread. "
                "Oil portraits of Hargrove ancestors lining the walls — heavy gilt frames. "
                "Domed skylight at the top of the well — cold grey light filtering down. "
                "Crystal chandelier suspended from dome, unlit, swaying faintly. "
                "The vertical spine of the house. "
                "[CAMERA: 24mm, f/8, looking upward from staircase base] "
                "[PALETTE: cold grey skylight from above, warm portrait frames, marble cream, deep shadow in stairwell] "
                "[PHYSICS: top-down skylight as key, portraits in shadow, chandelier silhouetted] "
                "[AESTHETIC: Victorian grand staircase, architectural drama, NO people, NO CGI] "
                "[FRAMING: staircase rising center, dome and chandelier at frame top, portraits flanking both sides]"
            ),
        },
        "E02": {
            "shot_type": "insert",
            "description": "INT. staircase landing — empty. Portrait of Harriet, balustrade detail",
            "prompt": (
                "INTERIOR — STAIRCASE LANDING. EMPTY. "
                "No people. "
                "The landing halfway up — where the staircase curves and pauses. "
                "The oil portrait of HARRIET HARGROVE dominates the wall here — "
                "stern Victorian woman in dark dress, piercing eyes, formal composition. "
                "Dark mahogany balustrade and newel post in foreground. "
                "Cold grey light from skylight above. "
                "The portrait watches whoever ascends. It has always watched. "
                "[CAMERA: 28mm, f/5.6, static, eye-level at landing height] "
                "[PALETTE: dark gilt portrait frame, cool grey light on painted face, dark mahogany balustrade] "
                "[PHYSICS: skylight top-down fill, portrait face subtly lit as if internally illuminated] "
                "[AESTHETIC: Victorian portrait authority, architectural stillness, NO people, NO CGI] "
                "[FRAMING: Harriet's portrait fills left 60% of frame, balustrade foreground-right, staircase beyond]"
            ),
        },
        "E03": {
            "shot_type": "insert",
            "description": "INSERT — carved newel post detail, or brass carpet rod, or portrait eye",
            "prompt": (
                "EXTREME CLOSE INSERT. The carved mahogany newel post at the staircase base. "
                "Victorian foliage carving, dark and heavy. Hand-worn smooth at the top by decades of passing grip. "
                "A brass carpet rod lies across the tread beside it, slightly loose. "
                "The texture of a house that has held many hands. "
                "[CAMERA: 100mm macro, f/2.8, static, looking across at carved detail] "
                "[PALETTE: dark mahogany brown, brass warm detail, carpet burgundy red, shadow in carved recesses] "
                "[PHYSICS: side-raking light picks out carved relief, deep shadow in recesses] "
                "[AESTHETIC: Victorian craftsmanship detail, tactile worn surfaces, NO CGI] "
                "[FRAMING: newel post carving fills frame, brass rod horizontal accent below]"
            ),
        },
    },

    "HARGROVE ESTATE - FRONT DRIVE": {
        "E01": {
            "shot_type": "establishing",
            "description": "EXT. front drive, iron gates, gravel, mansion facade, morning",
            "prompt": (
                "EXTERIOR ESTABLISHING. The front drive of Hargrove Estate. "
                "Looking from inside the iron gates toward the mansion. "
                "Raked gravel forecourt, overgrown at edges where it meets the lawn. "
                "The Victorian limestone facade directly ahead — symmetrical, imposing. "
                "Copper beeches lining the drive. Morning light, grey sky. "
                "A car or vehicle detail suggests contemporary arrival against Victorian backdrop. "
                "[CAMERA: 24mm, f/8, low angle from gate toward house] "
                "[PALETTE: grey limestone, copper beech bronze, grey gravel, morning grey-blue sky] "
                "[PHYSICS: flat overcast morning diffusion, no hard shadow, cool even light] "
                "[AESTHETIC: Victorian estate exterior, arrival geography, NO people, NO CGI] "
                "[FRAMING: drive leads eye to mansion centered at end, copper beeches flanking, gates edge of frame]"
            ),
        },
        "E02": {
            "shot_type": "insert",
            "description": "EXT. forecourt detail — gravel, ivy, estate stonework close",
            "prompt": (
                "EXTERIOR CLOSE — FORECOURT DETAIL. "
                "Gravel at the forecourt edge where it meets the estate lawn. "
                "Moss pushing through the gravel at the margin. "
                "The stone plinths of the forecourt steps — limestone, weathered. "
                "Ivy runner crossing the base of the estate wall, tendrils reaching. "
                "This place has not been properly maintained in years. "
                "[CAMERA: 50mm, f/4, static, low angle] "
                "[PALETTE: grey gravel, moss green, limestone white-grey, ivy dark green] "
                "[PHYSICS: flat overcast light, no shadow, moisture in the surfaces] "
                "[AESTHETIC: Victorian estate detail, neglect and presence, NO people, NO CGI] "
                "[FRAMING: gravel and moss foreground, step plinth middle, wall and ivy background]"
            ),
        },
        "E03": {
            "shot_type": "insert",
            "description": "INSERT — iron gate latch, or door knocker, or gravel underfoot",
            "prompt": (
                "EXTREME CLOSE INSERT. The iron latch of the estate gate. "
                "Heavy black ironwork, rust showing through old paint at the wear points. "
                "The latch mechanism — a finger-bar, cold to touch. "
                "This gate has opened for thirty years of visitors. Now it opens for the last time. "
                "[CAMERA: 100mm macro, f/2.8, static] "
                "[PALETTE: iron black, rust orange at wear points, cold grey background] "
                "[PHYSICS: flat overcast, raking light from side picking out rust texture] "
                "[AESTHETIC: Victorian ironwork detail, tactile cold metal, NO CGI] "
                "[FRAMING: latch mechanism fills frame, rust detail visible, gate rail beyond soft]"
            ),
        },
    },

    "HARGROVE ESTATE - EXTERIOR WIDE": {
        "E01": {
            "shot_type": "establishing",
            "description": "Wide exterior — full estate facade, grounds, sky",
            "prompt": (
                "WIDE EXTERIOR — FULL ESTATE. "
                "Hargrove Estate from the road or far field — the complete Victorian mansion. "
                "Limestone facade, symmetrical wings, Victorian gothic detail. "
                "Ivy and wisteria claiming the east wing. "
                "Rolling grounds, copper beeches, iron perimeter fence. "
                "Grey Yorkshire sky. Morning mist on the lawns. "
                "The house as a complete thing — massive, lonely, holding its secrets. "
                "[CAMERA: 24mm ultra-wide, f/11, very slight low angle, maximum depth] "
                "[PALETTE: grey limestone, deep copper beech bronze, grey-white sky, green-grey lawns] "
                "[PHYSICS: flat overcast diffusion, no direct sun, slight atmospheric haze at distance] "
                "[AESTHETIC: Victorian estate establishing, gothic grandeur, NO people, NO CGI] "
                "[FRAMING: full mansion centered, grounds foreground, sky upper 30%, copper beeches flanking]"
            ),
        },
        "E02": {
            "shot_type": "insert",
            "description": "EXT. grounds detail — fence, lawn, distant wing",
            "prompt": (
                "EXTERIOR DETAIL — ESTATE GROUNDS. "
                "The iron perimeter fence running across frame. "
                "Beyond it: the lawn, mist still lying low over the grass. "
                "A corner tower of the mansion visible in middle distance. "
                "This is the boundary between the outside world and what the house contains. "
                "[CAMERA: 50mm, f/4, static, eye-level] "
                "[PALETTE: iron black fence, white mist on green lawn, grey limestone tower] "
                "[PHYSICS: morning mist diffusion, cool even light, atmospheric depth] "
                "[AESTHETIC: Victorian estate perimeter, threshold feeling, NO people, NO CGI] "
                "[FRAMING: fence horizontal across lower frame, mist-covered lawn beyond, tower middle-distance]"
            ),
        },
        "E03": {
            "shot_type": "insert",
            "description": "INSERT — estate nameplate, or chimney stack, or weathervane",
            "prompt": (
                "EXTREME CLOSE INSERT. A weathervane atop one of the estate's chimney stacks. "
                "Copper, green with oxidation, in the form of a horse or cockerel. "
                "Still in the windless morning. "
                "Grey sky behind it. The estate marking its claim on the sky. "
                "[CAMERA: 200mm telephoto, f/5.6, static compressed] "
                "[PALETTE: oxidized copper green, grey sky, chimney brick red-brown] "
                "[PHYSICS: flat sky diffusion, silhouette quality, green patina detail] "
                "[AESTHETIC: Victorian architectural detail, estate identity, NO CGI] "
                "[FRAMING: weathervane centered against grey sky, chimney stack below, no horizon visible]"
            ),
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# AUDIT FINDINGS
# ─────────────────────────────────────────────────────────────────────────────

AUDIT_RESULTS = {
    "001_E01": {"verdict": "MISMATCH", "issue": "ACTION= character beat (Eleanor pushes open doors). Should be EXT. iron gates establishing."},
    "001_E02": {"verdict": "CORRECT",  "issue": ""},
    "001_E03": {"verdict": "MISMATCH", "issue": "ACTION= character beat (Thomas trails hand on banister). Should be door handle insert."},
    "002_E01": {"verdict": "MISMATCH", "issue": "ACTION= character beat (Nadia moves through library). Should be EXT. library wing exterior."},
    "002_E02": {"verdict": "CORRECT",  "issue": ""},
    "002_E03": {"verdict": "MISMATCH", "issue": "ACTION= character beat (Nadia catches falling letter). Should be book spine/letter insert."},
    "003_E01": {"verdict": "CORRECT",  "issue": ""},
    "003_E02": {"verdict": "WEAK",     "issue": "'The room breathes' — vague. Should describe ghost-white dust sheets, Steinway, silver candelabras."},
    "003_E03": {"verdict": "CORRECT",  "issue": ""},
    "005_E01": {"verdict": "CORRECT",  "issue": ""},
    "005_E02": {"verdict": "WEAK",     "issue": "'The room breathes. heavy curtains' — vague. Should describe four-poster, vanity, tarnished silver."},
    "005_E03": {"verdict": "CORRECT",  "issue": ""},
    "006_E01": {"verdict": "CORRECT",  "issue": ""},
    "006_E02": {"verdict": "WEAK",     "issue": "'The room breathes. copper pots' — vague. Should describe range glow, hanging pots, flagstones."},
    "006_E03": {"verdict": "CORRECT",  "issue": ""},
}

# Scenes without E-shots (need them added if inject_tone_shots() is called):
MISSING_E_SHOTS = {
    "004": "HARGROVE ESTATE - GARDEN",
    "007": "HARGROVE ESTATE - MASTER BEDROOM",
    "008": "HARGROVE ESTATE - GRAND STAIRCASE",
    "009": "HARGROVE ESTATE - FRONT DRIVE",
    "010": "HARGROVE ESTATE - DRAWING ROOM",
    "011": "HARGROVE ESTATE - LIBRARY",
    "012": "HARGROVE ESTATE - GRAND FOYER",
    "013": "HARGROVE ESTATE - EXTERIOR WIDE",
}

# ─────────────────────────────────────────────────────────────────────────────
# FIX FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def build_e_prompt(location: str, slot: str, beat_atmosphere: str = "") -> str:
    """Build a spatially-correct E-shot prompt from the SPATIAL_MAP."""
    # Find location key
    loc_key = None
    for key in SPATIAL_MAP:
        if key in location.upper() or location.upper() in key:
            loc_key = key
            break
    if not loc_key:
        return ""

    slot_data = SPATIAL_MAP[loc_key].get(slot.upper(), {})
    if not slot_data:
        return ""

    base = slot_data["prompt"]

    # Append realism anchor + soundscape slot
    full_prompt = f"{REALISM_ANCHOR}, environmental photography\n{base}"
    if beat_atmosphere:
        full_prompt += f"\n[MOOD: {beat_atmosphere}]"
    full_prompt += "\n[SOUNDSCAPE: see _soundscape_signature for scene tonal direction]"
    return full_prompt


def fix_e_shots():
    with open(SHOT_PLAN) as f:
        data = json.load(f)
    is_list = isinstance(data, list)
    shots = data if is_list else data["shots"]

    fixed = 0
    upgraded = 0

    for shot in shots:
        sid = shot.get("shot_id", "")
        if "_E0" not in sid:
            continue

        slot = "E" + sid.split("_E")[1]  # "E01", "E02", or "E03"
        location = shot.get("location", "")
        beat_atm = shot.get("_beat_atmosphere", "")
        verdict = AUDIT_RESULTS.get(sid, {}).get("verdict", "")

        if verdict == "MISMATCH":
            new_prompt = build_e_prompt(location, slot, beat_atm)
            if new_prompt:
                shot["_nano_prompt_pre_spatial"] = shot.get("nano_prompt", "")
                shot["nano_prompt"] = new_prompt
                shot["_spatial_map_applied"] = True
                shot["_spatial_map_slot"] = slot
                fixed += 1
                print(f"  FIXED {sid}: {AUDIT_RESULTS[sid]['issue'][:60]}")

        elif verdict == "WEAK":
            new_prompt = build_e_prompt(location, slot, beat_atm)
            if new_prompt:
                shot["_nano_prompt_pre_spatial"] = shot.get("nano_prompt", "")
                shot["nano_prompt"] = new_prompt
                shot["_spatial_map_applied"] = True
                shot["_spatial_map_slot"] = slot
                upgraded += 1
                print(f"  UPGRADED {sid}: replaced vague atmosphere with spatial detail")

    with open(SHOT_PLAN, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nFixed: {fixed} mismatches")
    print(f"Upgraded: {upgraded} weak prompts")
    print(f"Unchanged: {len([s for s in shots if '_E0' in s.get('shot_id','')]) - fixed - upgraded} correct shots")
    return fixed, upgraded


if __name__ == "__main__":
    print("ATLAS E-Shot Spatial Map Fixer V31.0")
    print("=" * 60)
    print("\nAUDIT RESULTS:")
    for sid, result in AUDIT_RESULTS.items():
        icon = "❌" if result["verdict"] == "MISMATCH" else ("⚠️" if result["verdict"] == "WEAK" else "✅")
        print(f"  {icon} {sid}: {result['verdict']}" + (f" — {result['issue'][:70]}" if result['issue'] else ""))

    print("\nMISSING E-SHOT SETS (scenes 004, 007-013 have no E-shots):")
    for scene_id, loc in MISSING_E_SHOTS.items():
        print(f"  Scene {scene_id}: {loc}")

    print("\nFIXING MISMATCHES + UPGRADING WEAK PROMPTS...")
    fixed, upgraded = fix_e_shots()
    print("\nDone. Backup of old prompts in _nano_prompt_pre_spatial field on each shot.")
