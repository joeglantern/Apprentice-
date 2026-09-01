# 08. App design brief: space black, one codebase, human hands

Written 2026-09-01. The standing plan for the Expo app's look, structure, and
naming. The app ships as one Expo Router codebase for iOS, Android, and web.
Same look everywhere; only the layout responds to screen size and input type.

## 1. Naming (working placeholders, nothing final until the operator says so)

The project codename stays Ghost Agent internally. The target register is
evocative and abstract, the way Anthropic, Opus, Fable, Midjourney, Qwen and
Higgsfield read: borrowed from Latin, Greek, physics, and story language, not
literal descriptions.

| App name | Why | Model name | Why |
|---|---|---|---|
| Umbra | Latin, the darkest part of a shadow | Eidolon | Greek, a phantom likeness of a person |
| Vanta | from vantablack, the blackest material made | Sable | heraldic black, also the finest brush hair |
| Noir | black, chic, instant aesthetic signal | Echo | the model echoes the designer's work |
| Monolith | the mysterious black slab | Anima | Latin for soul |
| Nocturne | a composition for the night | Specter | the ghost, straight up |
| Gamut | the color range a device can render | Doppel | the designer's double |

Working placeholders until decided: app **Umbra**, model **Eidolon**.
Shadow and phantom fit a space black app running a designer's ghost, and
eidolon versions cleanly (eidolon-layout-1, eidolon-style-1). Check
trademark collisions before anything ships publicly; most single-word names
have some existing use somewhere.

## 2. Design direction: space black

References worth stealing from (steal structure, not skin):

- Higgsfield (https://higgsfield.ai/): true black surfaces, one loud accent
  (#CDFF4D), tab-segmented creative modes, an Explore feed of trending
  output, model toggles inside the create surface. The closest overall
  template for us.
- Midjourney web (via Mobbin: https://mobbin.com/, screen set
  https://mobbin.com/explore/screens/5b639b3b-5efb-46af-b95f-09bc49952656):
  the masonry gallery as the front door, generation feels like browsing a
  portfolio, parameters folded into a compact bar.
- Krea (https://canvas.krea.ai/, docs https://docs.krea.ai/user-guide/features/realtime):
  ruthless minimalism, two-panel create surface, input left and live result
  right. Our web create screen should feel like this.
- Sora and ChatGPT images: iteration as conversation, every result carries
  its prompt and a remix affordance. Our chat screen borrows this.
- Mobbin (https://mobbin.com/) for any screen we are unsure about; search
  real apps before inventing a pattern.

### Palette

Flat solids only. No gradients anywhere, especially not purple-to-blue.

- bg base: #0A0A0B (near black, never pure #000 except OLED media view)
- surface: #141416, raised surface: #1C1C1F
- border/hairline: #2A2A2E
- text primary: #F2F2EF (warm off white), secondary: #9C9CA3
- accent, one only: #E8FF47 (acid lime, close cousin of Higgsfield's but
  ours; alternatives if it reads too borrowed: #FF6B4A coral or #FFC53D
  amber). Accent is for actions and progress, never for decoration.
- semantic: #4ADE80 success, #F87171 error, nothing else colored.

Texture: a faint monochrome grain (2 to 3 percent opacity) on large empty
surfaces so the black feels like paper, not a void. Made in-house, not a
stock PNG.

### Type

- Display and headings: Space Grotesk
  (https://fonts.google.com/specimen/Space+Grotesk), or Clash Display
  (https://www.fontshare.com/fonts/clash-display) if we want more attitude.
  Both free for commercial use; verify the Fontshare license text before
  bundling.
- Body and UI: Inter (https://fonts.google.com/specimen/Inter). Tabular
  numerals for timers and job counts.
- Mono accents (job ids, seeds, model tags): JetBrains Mono or Geist Mono.

### Iconography and assets

- Icons: Lucide (https://lucide.dev/), stroke width 1.5, never mixed with
  other sets. No sparkle icon for AI features; the model gets its own small
  wordmark chip (EIDOLON in mono caps) instead.
- Empty states: real example generations from our own pipeline, not
  illustrations.
- Never ship: stock 3D blob renders, glassmorphism cards, emoji in UI copy,
  em dashes in UI copy, typewriter text effects, floating particle
  backgrounds.

### Motion

Purposeful only, reanimated springs, 150 to 250ms, standard easing:

- press states scale to 0.97
- generation progress: a thin accent bar plus the plain-language stage line
  from the backend (planning, composing, rendering 2/3)
- renders arrive with a 200ms fade-up, no shimmer on content that is not
  loading
- layout transitions between breakpoints do not animate; they just are

## 3. Screens

1. Explore (home): masonry grid of finished generations, filter chips by
   kind (poster, image, logo) and aesthetic. Tap opens detail with prompt,
   seed, aesthetic version, and a Remix button. Midjourney pattern.
2. Create: prompt field, kind selector, size presets, aesthetic/brand kit
   selector as swatches, one Generate button. On web at >=1024px this
   becomes the Krea split: controls left, live result right.
3. Chat (iterate): a thread with the director model. Each assistant turn can
   carry a canvas preview card; quick actions under it (change headline,
   swap photo, recompose, export). This is the revision loop the backend
   already supports, surfaced as conversation. Sora pattern.
4. Canvas detail: the SVG canvas render, layer list, per-layer actions
   (edit text inline, regenerate image zone, nudge). Export PNG.
5. Brand kits: saved palettes, logos, fonts per client; attach one to any
   generation.
6. Jobs: queue and history with live progress, retry on failure.
7. Settings: server, account, capture consent status readout (read-only
   mirror of the collector's state, honesty on display).

## 4. Responsive rules (one codebase)

- Breakpoints: under 768 is phone, 768 to 1023 is tablet/small web, 1024 and
  up is desktop web.
- Navigation: bottom tab bar on phone; left rail with labels on desktop.
- Explore grid: 2 columns phone, 3 tablet, 4 to 5 desktop, virtualized.
- Create: stacked on phone, split-panel on desktop.
- Content max width 1280 centered on desktop; media views full-bleed.
- Input awareness: hover states and keyboard shortcuts (enter to generate,
  slash to focus prompt) only where a fine pointer and hardware keyboard
  exist; detect with Platform.OS, useWindowDimensions, and pointer media
  where available, never user agent sniffing.
- Touch targets 44px minimum everywhere, including web.

## 5. Master design prompt

Paste-ready brief for generating mockups or building screens. Keep it intact:

> Design [screen] for Umbra, a mobile and web app where a small creative team
> generates on-brand graphics with a custom model called Eidolon. Space black
> interface: background #0A0A0B, surfaces #141416 and #1C1C1F, hairlines
> #2A2A2E, warm off-white text #F2F2EF, secondary #9C9CA3, single accent
> #E8FF47 used only for primary actions and progress. Flat solids, no
> gradients, faint monochrome grain on large surfaces. Space Grotesk for
> headings, Inter for body, mono for technical chips. Lucide icons at 1.5
> stroke. Dense but calm layout in the register of Higgsfield and Krea:
> generous 8pt spacing scale, hairline dividers, content-first, the
> generated artwork is always the hero. Motion is restrained spring
> micro-interactions only. Copy is short, human, lowercase-friendly,
> no emoji, no em dashes, no exclamation marks. Phone layout uses a bottom
> tab bar; desktop uses a left rail and wider grids. This should look like a
> tool a working designer respects, not a landing page.

## 6. Build order

1. tokens.ts (colors, spacing, type scale, radii) plus the grain asset
2. navigation shell responsive to breakpoints (tabs vs rail)
3. Create screen wired to the existing generate API
4. Jobs with live progress (the backend already streams stages)
5. Explore fed from generation history
6. Chat iterate on the revision endpoint
7. Canvas detail actions, brand kits, settings
8. motion pass, empty states, app icon and splash

Design tooling note: mockups can be seeded on a design canvas before code,
but with the API live it is usually faster to iterate in code behind a dev
flag. Decide per screen, not globally.
