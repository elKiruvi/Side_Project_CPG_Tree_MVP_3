# How to review this clinical pathway

## What you are reviewing

- This pathway was produced with AI assistance from the institutional
  protocol. It is a CANDIDATE pathway: it has passed structural and
  provenance validation but has NOT been clinically approved.
- Review the rules, logical operators, thresholds, treatments, branches,
  sequence, missing steps, and conflicts against the protocol you know.

## Before you start

1. Open `review_tree.html` — it is the main visual of the candidate pathway.
2. Read `review_summary.md` for the proposed pathway narrative.
3. Answer the questions in `review_questions.md`.
4. Use `evidence.md` to check the exact source page and text for each item.
   Items marked VISUAL SOURCE / MANUAL REVIEW REQUIRED come from figures or
   tables that could not be read as text and need your own verification.

## What the status labels mean

- PROPOSED — candidate content pending your review.
- BLOCKED — candidate content with unresolved evidence; review it and tell us
  how to resolve it.
- Issues — known conflicts or uncertainties; your input decides them.

## How to record your review

Use the file `review_template.json` (one per reviewer). For each rule or
relationship you reviewed, add an entry under `decisions` with:

- `decision_id`: any unique short id, e.g. `rev1-r18`.
- `subject_type`: `RULE` or `RELATION`.
- `item_id`: the rule or relationship id from the catalog.
- `candidate_revision` and `content_hash`: copy them from the catalog entry —
  never change them.
- `verdict`: one of
  - `APPROVE` — I agree with this item as written;
  - `REJECT` — this item is wrong and must not become clinical knowledge;
  - `REQUEST_CHANGES` — the idea is acceptable but must change; put the
    requested correction under `proposed_corrections` and explain under
    `rationale`;
  - `NEEDS_CLARIFICATION` — I need more context to decide;
  - `DEFER` — not my area; someone else should decide;
  - `ABSTAIN` — no position.
- `reviewer_id`, `reviewed_at` (ISO date), and any comments.

If something is MISSING from the pathway, add an entry under `feedback` with
a `feedback_type` such as `MISSING_RULE`, `MISSING_RELATION`, `MISSING_BRANCH`,
`MISSING_CONDITION`, `MISSING_ACTION`, or `MISSING_EVIDENCE`, and describe
what is missing under `description` (and `proposed_content` if you can).

Do not edit any other file in this package. Return the completed template to
the project team. Your decisions are recorded exactly as submitted and never
silently changed.
