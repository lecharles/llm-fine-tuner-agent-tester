# Design System

The visual language for LLM Fine Tuner & Agent Tester. Linear-grounded restraint,
first-class light and dark modes, a small semantic accent set. The authoritative
tokens live in `frontend/src/theme.css`; this document is the reasoning behind them.

Reference inspirations: Linear (restraint, near-black neutrals, hairline borders),
with a small identity nod to the author's own Dyssonance API Catalog (violet + coral)
and Unsloth Studio (soft functional accents). The result is its own system.

## Principles

- Neutrals do the structural work. A near-black ramp (dark) or off-white ramp
  (light) separates and elevates components. Color is not the layout tool.
- Accents are scarce and semantic. Six roles, each with one job. Never a rainbow.
- Color means one thing. A hue used for a state is never reused for an identity.
- Light and dark are peers, not a theme and an afterthought. Every token has a
  value in both. Accents deepen in light mode to hold contrast on white.
- Tokens are named by role, not by hue, so a theme flip swaps values, not components.

## Modes

Dark is the default. Light is a first-class override. The toggle sets
`data-theme="light"` on `<html>`; every token flips.

The key mechanism: dark-mode accents run bright to pop on near-black; the same
hues deepen in light mode to meet WCAG 2.0 AA contrast on white. Gold is the
clearest example, a punchy `#E7B646` on black becomes a bronzed `#AE770E` on
white, because pure gold on white is unreadable. One palette serves both modes
honestly because each side is tuned for its background.

## Neutral ramp

| Token | Dark | Light | Use |
| --- | --- | --- | --- |
| `--bg` | `#0B0C0E` | `#F7F6F2` | Page background |
| `--surface` | `#14161A` | `#FFFFFF` | Cards, panels |
| `--surface-elevated` | `#1C1F25` | `#FFFFFF` + shadow | Popovers, raised surfaces |
| `--border` | `#2A2D34` | `#E5E3DD` | Hairline borders (0.5px) |
| `--text` | `#ECEDEF` | `#1A1B1E` | Primary text |
| `--text-muted` | `#8A8F99` | `#6A6E76` | Secondary text, hints |

## Accents (by role)

| Token | Role | Dark | Light |
| --- | --- | --- | --- |
| `--primary` | Brand identity, the fine-tuned model | `#7C74F2` | `#5A50D6` |
| `--success` | Completed, healthy | `#3ECF8E` | `#1E9B55` |
| `--warning` | Running, caution | `#E7B646` | `#AE770E` |
| `--danger` | Failed, destructive | `#F2646F` | `#D53A44` |
| `--info` | Neutral information | `#55A6F2` | `#2569C4` |
| `--hosted` | Any third-party hosted model | `#F0885C` | `#D5583B` |

Violet is the identity color: it marks the app's whole reason to exist, the
fine-tuned model. Each accent also has a low-opacity `*-tint` for chips, badges,
and selected rows. Text on a solid `--primary` button uses `--on-primary`.

## Compare-column colors

The four-way compare groups columns by what kind of model they are, so the eye
reads "mine vs the baseline vs the field" at a glance:

- Fine-tuned model → `--primary` (violet). Your model, the star.
- Vanilla base model → `--text-muted` (neutral). The untuned baseline it beats.
- Hosted models → `--hosted` (coral), the SAME color for every third-party model.

The hosted color is deliberately shared across all third-party models (OpenAI,
Anthropic, and later Gemini, Mistral, and others). They are one category, the
external benchmarks, so they read as one family. Per-vendor colors would become
noise and a maintenance tax as models are added. The bucket is the meaning.

## Type

- UI: a clean system sans (`--font-sans`).
- Code, hex values, model ids, curl: monospace (`--font-mono`).
- Signature treatment (from the references): uppercase, letter-spaced mono for
  small section labels; a lighter weight for large display headings; muted gray
  body against brighter headings.

## Accessibility

- All text/background pairs target WCAG 2.0 AA. Accents deepen in light mode
  specifically to clear the 4.5:1 threshold on white (large text 3:1).
- On a colored (tinted) background, text uses a deep shade of that same hue,
  never plain black or generic gray.
- Borders are 0.5px hairlines; elevation is color (dark) or shadow (light),
  never heavy outlines.

## How it is applied

`frontend/src/theme.css` is the single source of truth. The frontend is built
unstyled first (function before form); the theme is applied as the final step
over a working app, so styling never masks a logic bug. Components read tokens
only, never hardcoded hex, which is what keeps light and dark honest and the
system consistent.
