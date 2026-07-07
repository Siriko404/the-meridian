# Panel Design — UI v2 Spec Audit

**Panel size:** 1 expert (user-set: "one fable agent") · **Model:** fable ·
**Effort:** inherits session · **Budget call:** user chose single-agent maximum-thoroughness
over a multi-expert split.

| Expert | Facet | Duties (8) | Sources | must_read |
|---|---|---|---|---|
| `spec-fidelity` | Design-spec fidelity: rules coverage, code-reality feasibility, audit closure, internal consistency | RULE SWEEP · AUDIT CLOSURE · CODE-REALITY CHECK · INTERNAL CONSISTENCY · TIMER/ASYNC SOUNDNESS · TRADE PROTOCOL SOUNDNESS · VISIBILITY SWEEP · MOMENT COMPLETENESS | 23 (guide, spec, audit, status, 10 engine, 5 server/observe, spike, 2 v1-UI) | 19 |

Tools: Read, Grep, Glob, Bash (journal appends only). No web, no edits, no subagents.
Prompt: `prompts/spec-fidelity.md` — generated mechanically (`generate-prompts.js`,
hard-rules block verified byte-identical). Never hand-edited.

**Prompt ratified by Sina:** 2026-07-08 (AskUserQuestion: "Ratify prompt")
**Manifest ratified by Sina:** 2026-07-08 (AskUserQuestion: "Ratify manifest")
