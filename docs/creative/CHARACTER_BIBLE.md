# Character Bible v2: Arka & Lipa

Status: **v2 approved by the owner and locked as `character_version = 2`** (2026-11-05). This version replaces Kai & Needle (v1). The owner supplied the Arka & Lipa design and its React/SVG rig. Claude polished the shapes and motion (DECISIONS, 2026-11-05).

The rig is pure React/SVG in `remotion/src/rig/`. Poses are plain numbers, so any two poses can be blended, the arms and legs use 2-bone IK, and the scarf follows the wind. The reference sheet (`docs/creative/reference_sheet_v2.png`, the `CharacterSheet` still) and the motion check (`docs/creative/rig_v2_motion_check.mp4`, the `RigCheck` composition) are rendered from the same rig the episodes use, so the sheet and the videos cannot drift apart.

Any change to the look, the rig IDs or the motion rules is a new character version and needs owner approval again.

---

## Arka (hero, speaker id `arka`)

### Who
- A 10-year-old young explorer who keeps a field journal of every mystery and goes out to find the answer instead of just being told.
- Discovers answers *with* the viewer and never lectures. Curious, brave, playful, humble. Makes guesses, some of them wrong, and checks them.

### Look
| Element | Spec |
|---|---|
| Proportions | Chibi explorer: the head and hat make up the top half of the figure (about 410 rig units, feet to hat top). Big anime eyes with amber irises and two highlights |
| Silhouette | Wide-brimmed **safari sun hat** with a leaf, a backpack with a rolled bedroll, and a scarf tail flying behind. It must read as Arka in solid black |
| Hat | Sunhat Cream `#F4EBD6` with a Satchel Brown `#9A6438` band and a **brass compass pin** (Compass Brass `#D2A040`) |
| Hair / eyes | Honey Hair `#C98A3D`, spiky fringe. Amber Iris `#E59A2B` |
| Skin | `#F7D2AE`, with blush on the cheeks |
| Scarf | Scarf Teal `#2E9E7F` with a cream **kawung** motif. Its tail flows in the wind (`scarfWind`) |
| Shirt / shorts | Cream explorer shirt with pockets and buttons; Trail Khaki `#B99B6B` shorts |
| Backpack | Explorer Navy `#24305E` / River Blue `#3F7FC6` bedroll, Satchel Brown straps |
| Sneakers | Ember Coral `#F26B4C`, cream soles, teal socks |
| Outline | Ink Plum `#2B2240`. Every shape is outlined |

### Expressions (rig IDs)
| ID | Use |
|---|---|
| `neutral` | listening, default |
| `curious` | asking, noticing |
| `surprised` | discoveries, twists |
| `delighted` | success, fun facts |
| `puzzled` | wrong guesses (question-mark effect) |
| `determined` | "let's find out" |
| `worried` | "uh-oh", never fear (sweat drop) |
| `laughing` | jokes, celebration |
| `wink` | playful asides |
| `awe` | big reveals (star eyes) |

Lip-sync: while Arka speaks, the mouth switches to `talk` and opens with the voice loudness on every frame, and it closes between syllables. Arka blinks naturally about every 3–4 s.

### Poses (rig IDs)
`idle`, `talk`, `point`, `think` (hand at chin), `surprised`, `celebrate`, `walk`, `hold_map`, `hold_compass`, `look_out` (spyglass), `crouch`, `wave`, `jump`, `look_up`.

Actions layered on top: `wave`, `nod`, `jump`, `gasp`, `look_around`, `tap_compass`, `shrug`, `scratch_head`.

### Body language
- Leans *into* discoveries and steps back from surprises.
- Talks with one hand. Points at what the viewer should look at.
- Never frozen: there is always a breath, a weight shift, a blink or a gesture.

---

## Lipa (companion, speaker id `lipa`)

### Who
- A small origami bird folded from Arka's old expedition map. Its wings still show bits of rivers, trails and a compass star.
- It glows when it finds a trail, a clue or the answer.
- Curious and literal-minded. Asks the "silly" questions kids are shy to ask, and takes figures of speech literally.

### Look
| Element | Spec |
|---|---|
| Shape | Faceted paper bird: a folded body, a split tail and two big folded wings. Map Parchment `#F3E4C0` with a darker underside |
| Map detail | The top of each wing shows a River Blue river, a dashed Ember Coral route and a brass compass star. The underside is plain paper |
| Beak | Compass Brass, a two-part beak that opens to speak |
| Face | Dot eyes with a highlight and small blush. Eyes and beak carry the acting |
| Glow | Lantern Glow `#FFD872` halo and a sparkle trail. Brighter when it finds the trail |
| Size | About 1/4 of Arka's height at the same depth. Flies, glides or perches, never stands on the ground |

### Expressions
`neutral`, `curious`, `surprised`, `delighted`, `puzzled`, `determined`, `worried`, `laughing`.

### Poses and actions
- Poses: `float`, `flap`, `glide`, `dive`, `perch`, `loop`.
- Actions: `sparkle`, `loop_the_loop`, `dim`, `flash`, `wiggle`.

### Movement
- Never parked on one side. Flies around Arka, perches on a shoulder or the hat brim, dives toward a clue.

---

## Motion (rig v2 polish)
These rules are built into the rig and the scene renderer (`remotion/src/scene/puppets.ts`), so every episode gets them automatically:
1. **Soft joints.** Elbows and knees are drawn as a rounded fillet, never a sharp corner.
2. **Smooth gait.** In the walk cycle, feet lift and plant on eased curves (zero speed at lift-off and contact). The hips bob and sway over the standing foot, there is a small squash on contact, and the arms counter-swing. No `|sin|` cusps or sudden pops.
3. **Blended poses.** A pose change between shots blends over 10 frames with a small overshoot, never a snap.
4. **Props never pop.** The map, compass and spyglass shrink out and grow in during a blend.
5. **Follow-through.** The head trails the body slightly when Arka bobs, jumps or rolls.
6. **Anticipation.** Jumps start with a small crouch, stretch in the air and squash on landing.
7. **Living stillness.** A standing character keeps a slow weight shift and breathing. Talking adds small hand and head beats.
8. **Paper flight.** Lipa's wingbeat is a quick power downstroke and a slower upstroke. The wing tips trail the roots, so the paper flexes, and the body lifts on each downstroke.

## Consistency rules
1. Only rig IDs from `config/catalogue/rig_v2.yaml` exist. Unknown poses or expressions fail the storyboard check. Old rig v1 storyboards (`kai`/`needle`) still load and render through ID aliases.
2. Colours come from `remotion/src/rig/palette.ts`. No per-episode recolouring.
3. Arka and Lipa are never drawn by an image model. Every pixel comes from the rig, so they look the same in every episode.
4. Lipa is never bigger than Arka's head in the same shot (except in its own close-up).
5. No scary expressions. `worried` is the strongest negative emotion.

## Do / don't
| Do | Don't |
|---|---|
| Lean in, point, react with the whole body | Stand still and lecture to camera |
| Let Lipa ask the obvious question and light up the trail | Make Lipa a second narrator |
| Show Arka being wrong, then figuring it out | Make Arka a know-it-all |
| Keep the hat, compass pin, teal scarf and coral sneakers visible in wide shots | Change Arka's outfit between episodes (v2 has one outfit) |
