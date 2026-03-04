---
date: 2026-02-16
tags: [decision, thesis, latex, template, formatting]
---

# ADR-005: Lock DSW Thesis LaTeX Template (70/2024)

## Context

The thesis PDF must comply with DSW requirements from Zarządzenie 70/2024 (especially Załącznik 4 and title page model from Załącznik 5).

During template tuning, multiple spacing/layout values were tested. Small changes caused visible drift from the official model and occasional regressions (title page overflow or incorrect vertical rhythm).

## Decision

Adopt and lock the current thesis template settings as the project baseline.

Primary files:

- `thesis/templates/dsw-thesis.latex`
- `thesis/templates/titlepage.latex`
- `thesis/metadata.yaml`

### Locked formatting settings

#### Global editorial defaults (`thesis/templates/dsw-thesis.latex`)

- Paper: A4, margins 2.5 cm (from metadata geometry)
- Font: Times New Roman, 12 pt
- Body line spacing: `linestretch: 1.25` (Word-like 1.5 behavior in LaTeX)
- Paragraph indent: `1.25cm`
- Paragraph spacing after: `0pt`
- Hyphenation: disabled (`hyphenat` + `none`)
- Pagination: continuous digits in right-bottom corner

#### Heading spacing

- `\section`: before `10pt`, after `12pt`
- `\subsection`: before `10pt`, after `12pt`

#### Title page (`thesis/templates/titlepage.latex`)

- No logo on first page
- 11 pt text with `\setstretch{1.5}`
- Layout tuned to match `template_ostateczny.pdf` (single-page first page model)

## Validation performed

- Pixel-style + coordinate comparison against:
  - `template_ostateczny.pdf` (primary first-page target)
- Checked deltas for key anchors and vertical gaps:
  - specialization -> name
  - title -> work type
  - city/year vertical position
- Result reached near-identity layout for top/middle blocks and close match for lower block with real content.

## Guardrails For Future AI Agents

1. Do not change spacing in `thesis/templates/titlepage.latex` unless user explicitly asks.
2. Do not reintroduce logo on first page unless user explicitly asks.
3. Do not move page numbers to center or use `Strona x/y` in thesis body. Keep right-bottom numeric pagination.
4. Do not change `\parskip`, heading spacing, margins, or line spacing without explicit user approval.
5. If formatting is questioned, compare against `template_ostateczny.pdf` first, then report numeric deltas before editing.
6. Keep first page one-page only; any change causing overflow to page 2 must be reverted.
7. Prefer minimal edits; avoid broad template refactors.

## Non-goals

This ADR does not confirm full diploma formal acceptance (length, bibliography count per track, APD print/control number, signed statements). It only locks the LaTeX formatting baseline.
