---
name: niche
description: Recreate the "Sweet Dreams / bandaged man" niche fashion edit (17 fast beat-synced shots, 16.5 s, 9:16) starring the user, built from a photo they attach. Use when the user types /niche, sends a selfie and asks for "the niche video", or wants to star in this surreal AI fashion edit.
argument-hint: "[attach your photo] [optional: song file]"
---

# /niche — put the user in the "Sweet Dreams" niche edit

You produce a 16.5 s vertical AI video that recreates the **style, pacing and shot
structure** of the reference edit, with the **user's face and body as the HERO**,
then recommend (and optionally sync) the song. Zero errors is the bar: every gate
below is mandatory.

- Full shot-by-shot spec: [references/shotlist.md](references/shotlist.md)
- Cut timings: [references/timeline.json](references/timeline.json)
- Final edit: [scripts/assemble.py](scripts/assemble.py)

Talk to the user in their language (Portuguese if they write in Portuguese). Be brief.

## Step 0 — Gate the inputs (stop if any fails)

1. **Photo attached?** If not, ask for it and stop.
2. **Photo quality** — open it and check: one person, face clearly visible and
   frontal or 3/4, eyes open, no sunglasses/mask/heavy filter, sharp, ≥ 512 px on the
   face, good light. If it fails, say exactly what is wrong and ask for another.
   Two or three photos (front, 3/4, full body) improve likeness — ask once, optional.
3. **Consent** — the photo must be of the user themself (or someone who agreed).
   Never build this with a photo of another real person without consent.
4. **Generation access** — you need an image-edit model and an image-to-video model.
   Default provider: **fal.ai** (`FAL_KEY`). Check `echo ${FAL_KEY:+set}`. If missing,
   ask for the key through the environment's secure credential mechanism (never ask
   the user to paste it in chat). Without access, stop and say so — never fake output.
5. `ffmpeg`/`ffprobe` installed (`which ffmpeg ffprobe`).

## Step 1 — Lock the HERO identity

Write a short identity sheet from the photo: hair (color, length, style), face shape,
skin tone, eyebrows, facial hair, distinctive features. Reuse it verbatim in every
prompt. Copy the photo to `work/hero.jpg`. All work goes in `work/` (create it).

## Step 2 — Generate 17 keyframes (image edit, identity-preserving)

For each shot S1–S17 in `shotlist.md`, generate one 9:16 still (≥ 1080x1920 or the
model's closest vertical size) with an identity-preserving edit model, passing
`work/hero.jpg` as the reference image whenever the HERO or his lips appear
(S1–S5, S7–S13, S16). Good fal models: `fal-ai/nano-banana/edit`,
`fal-ai/flux-pro/kontext`, `fal-ai/bytedance/seedream/v4/edit` — check the fal
model page for the current name/params before calling.

Prompt template (fill from the shot row + identity sheet):

```
Vertical 9:16 photo, phone camera with hard on-camera flash, candid, slight
overexposure, saturated kitsch colors. [SHOT DESCRIPTION]. The man is the person in
the reference image: [IDENTITY SHEET]. He wears an olive-green field jacket with
silver studs on collar and shoulders, dark crewneck, dark straight jeans, black
loafers. Keep his face exactly as in the reference. Photorealistic, no text, no
watermark, no logos.
```

B&W shots (S6, S14, S15, S17) — no reference image needed:

```
Vertical 9:16 still from a 1930s black-and-white film, film grain, soft vignette.
A man whose entire head is wrapped in white gauze bandages, round sunglasses,
houndstooth overcoat, white gloves. [SHOT DESCRIPTION]. Original character, no text.
```

Extra rules: S7–S9 show the bandaged head but the exposed mouth/jaw must be the
HERO's, with **silver grills**. S16: the back patch reads exactly **"SWEET DREAMS"**
(red/pink embroidered letters) — regenerate until the spelling is perfect.

Fal call pattern (queue API):

```bash
curl -s -X POST "https://queue.fal.run/$MODEL" -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" -d @req.json   # returns status_url, response_url
curl -s "$STATUS_URL" -H "Authorization: Key $FAL_KEY"  # poll until COMPLETED
curl -s "$RESPONSE_URL" -H "Authorization: Key $FAL_KEY" # get the output URL
```

Upload `hero.jpg` first (fal storage upload, or pass a base64 data URI in `image_urls`).
Save as `work/key/S1.png` … `S17.png`.

### Gate A — keyframe QA (look at every image yourself)

Reject and regenerate (max 3 tries per shot, then tell the user) if any:
- HERO face doesn't clearly look like the photo (compare side by side)
- extra/missing fingers, melted hands, warped face, wrong number of people
- wrong outfit (jacket must be olive with studs), "SWEET DREAMS" misspelled
- any text, watermark, logo, or TikTok handle
- B&W shot not fully monochrome

Show the user a contact sheet of the 17 keyframes
(`ffmpeg -i work/key/S%d.png -vf "scale=270:-1,tile=6x3" work/sheet.jpg`) and ask
"aprovado?" before spending on video. Regenerate any shot they flag.

## Step 3 — Animate each keyframe (image-to-video)

Use an image-to-video model with the keyframe as the first frame, 9:16, shortest
duration it offers (usually 5 s; the editor trims). Good fal models: Kling
(`fal-ai/kling-video/.../image-to-video`), Veo (`fal-ai/veo3/.../image-to-video`),
Seedance (`fal-ai/bytedance/seedance/.../image-to-video`) — check the current name.
Motion prompt = the shot's action only, plus `handheld phone camera, subtle shake,
no cuts, no text`. Keep motion small except S2 (whip pan), S4 (cue strike),
S16 (flames grow, he turns and covers his face). Disable generated audio.
Save as `work/clips/S1.mp4` … `S17.mp4`.

### Gate B — clip QA

Extract 3 frames per clip (`-vf fps=1`) and check: face stays the HERO's through
the motion (no morphing), hands intact, no cut inside the clip, no text. Regenerate
failures (max 3). Use the most stable 0.4–2.5 s — the editor takes the middle.

## Step 4 — Pick the song and lock the beat

Recommend: **"Sweet Dreams (Are Made of This)" — Eurythmics** (1983). It matches the
patch on the jacket and its ~126 BPM fits the edit's measured ~129 BPM rhythm, so
every cut lands on a beat. On TikTok/Reels pick the **sped-up version** for the
closest match (~129 BPM); the original at 126 BPM also works with `--bpm 126`.

- If the user supplies the song file: find the first strong downbeat (use the
  synth riff's first hit) and pass it as `--audio-start`, with `--bpm` = the version's
  BPM (126 original; measure a sped-up file with ffmpeg onset analysis).
- If not: export silent and tell them to add the song in TikTok/CapCut starting on
  the riff's first hit (licensed music there avoids copyright mutes). Never download
  copyrighted audio from unofficial sources.

## Step 5 — Assemble

```bash
python3 .claude/skills/niche/scripts/assemble.py --clips work/clips \
  --out work/niche_final.mp4 --bpm 126 [--audio song.mp3 --audio-start 0.0]
```

The script fits each clip to 1080x1920 30 fps, trims to the timeline (snapped to the
beat grid when `--bpm` is given), applies the 1930s B&W grade to S6/S14/S15/S17,
concatenates, and verifies duration. It must print `"status": "PASS"`.

### Gate C — final QA (mandatory before delivering)

1. Extract one frame per shot midpoint and look at all 17: right order, HERO face
   consistent, no glitches, no text/watermarks.
2. `ffprobe` the file: 1080x1920, 30 fps, duration 16.5 ± 0.2 s.
3. If audio was muxed: confirm cuts sit on beats (spot-check 3 cuts).
Fix and re-run until all pass.

## Step 6 — Deliver

Send `work/niche_final.mp4` and reply in 3–5 lines: the file, the song
(name, artist, which version, where to start it), and a reminder to keep TikTok's
"AI-generated" label on when posting. Don't claim anything you didn't verify.

## Don'ts

- Don't reuse frames, footage or audio from the reference video or from any film.
- Don't add the original creator's handle, TikTok logos, or the outro card.
- Don't deliver if any gate failed — say which shot failed and why.
