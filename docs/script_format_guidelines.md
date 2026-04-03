# Script Format Guidelines (Mandatory)

To guarantee Auto Studio / Atlas can parse every episode:

## 1. File Structure
- Keep all Story Bible, outlines, scene cards, LTX guidance, wardrobe, and casting rules **above** a single delimiter line:
  ```
  ---SCREENPLAY---
  ```
- Everything **below** that delimiter must be parser-clean screenplay text (INT./EXT. headings, action, dialogue). No markdown headings, bullets, “Cut to”, “Show open”, or broadcast packaging.

## 2. Metadata vs Screenplay
- **Metadata section (above delimiter)** may contain:
  - Story bible entries, act outlines, scene cards
  - Director/writer notes
  - LTX template instructions, wardrobe locks
  - Alias map (e.g. `ARTHUR = ARTHUR GRAY`)
  - Stopwords list (terms that should never be treated as characters)
- **Screenplay section (below delimiter)** must include only:
  - Scene headings (INT./EXT. ... – TIME)
  - Action lines
  - Dialogue blocks with character names
  - Minimal transitions (SMASH CUT, FADE OUT) when necessary

## 3. Alias Map & Stopwords
- Provide alias mappings for shortened names so the casting agent keeps actors consistent.
- Provide a stopwords list (NIGHT, MORNING, SHOW OPEN, etc.) so those tokens are never cast as characters.

## 4. No Shot Directions in Screenplay Section
- Move “Cut to: (MCU)”, “Camera pans…”, “Commercial Break”, “Show Open/Bumper” into metadata.
- Describe cinematography and camera flow inside the LTX template, not inline in the screenplay.

## 5. Automation Pipeline
- Pre-processor should:
  1. Split the document at `---SCREENPLAY---`.
  2. Export metadata to `project_meta.json`.
  3. Export screenplay to `imported_script.txt`.
- Auto Studio imports metadata for director/writer agents, then parses the screenplay for casting + shot planning.

Following these rules keeps every script (Ravencroft or otherwise) machine-decodable and ready for 400+ episodes.
