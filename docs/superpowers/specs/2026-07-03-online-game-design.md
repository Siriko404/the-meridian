# Social Roulette — Online Playable (v1) Design

**Date:** 2026-07-03 · **Status:** spec (advisor-vetted) · **Process:** superpowers brainstorming

## Goal
An online room where people join by **invite code** and play Social Roulette in a
browser, **in real time**, powered by the **existing Python engine** — reachable from
anywhere with the host's PC **off** (free cloud host). Empty seats fill with **random
bots** so a 5-player game can start with 1+ humans.

## Non-goals (v1) — explicit
- **LLM agents.** Deferred. The bot *seat* is abstract (a `policy`), so swapping
  random→LLM is a drop-in for the *policy interface* — but the LLM still needs its own
  NL state-rendering + a real talk-phase chatroom. Those are separate future builds, not free.
- **The spec's timed talk→decision negotiation.** v1 = turn-by-turn play with a
  **cosmetic chat overlay** (chat is social only; the engine does not read it).
- **Strict timers/timeouts.** Untimed v1; disconnect→bot prevents walk-away hangs.
- **Durable rooms** across restarts (in-memory; persistence is later).

## Reused — verified interactive-ready (traced in the engine)
- `state.current_id` — whose turn (engine tracks it).
- `legal_actions(state, pid)` — that seat's legal options right now (already gates
  Speak/Trade behind `not bonus_pending`).
- `engine.step(state, pid, action)` — apply ONE action. **SHOOT advances the turn;
  other actions don't** → a human turn = "keep picking legal actions until you shoot",
  with no re-implementation of turn/bonus/reload/elimination (all inside the engine).
- `Extras` (announced chamber counts + magnifier peek) per seat; recorder/event schema for logging.

## New components
1. **Per-seat view serializer** — *INTEGRITY-CRITICAL.* Given `(state, seat)`, emit a JSON
   view = **public info** (all teams, lives, flips, item-type counts, announced chamber
   counts, message/event feed) **+ ONLY that seat's own inventory + its `legal_actions`**.
   The full `GameState` MUST NEVER be serialized to a client (would leak other players'
   hands + shell order). This is NOT `encode_obs` (that's numeric + ego-relativized for the net).
2. **Room state-machine (async).** Per room: `{GameState, seat→client, Extras, recorder,
   waiting_on_seat}`. Event-driven: on client action → **acquire per-room asyncio lock** →
   **re-validate** against `legal_actions` (never trust the client) → `engine.step` →
   broadcast fresh per-seat views → set `waiting_on = state.current_id` → if that seat is a
   bot, auto-step. The lock prevents two messages mutating one `GameState` concurrently.
3. **WebSocket protocol.** client→server: `join{code,name}`, `action{index}`, `chat{text}`.
   server→client: `view{...per-seat...}`, `event{delta}`, `chat{from,text}`, `lobby{...}`, `end{winner}`.
4. **Room / invite manager.** Create room → random invite code → host lobby → start →
   empty seats become random bots → run.
5. **Generic UI** (one static HTML+JS file, no build step). Renders: the table (each
   player: team color, lives, alive, public item-count; self: full hand), chamber counts,
   event/message feed, chat box, and **MY legal-action buttons rendered generically from
   `view.legal_actions`** — no bespoke UI per item/flip/trade. Click → send `action{index}`.
6. **Bot seat.** `policy(state, pid) -> action` = `random_policy` now; swappable later.
7. **Hosting.** FastAPI serves the static UI + WS. Deploy to **Render free** (public URL,
   PC-independent). In-memory rooms (ephemeral — acceptable for play sessions).

## Integrity / security (advisor gap 1 — load-bearing)
- **Server is authoritative.** Every action re-validated vs `legal_actions(state, seat)`;
  illegal → rejected, no state change.
- **Per-seat views only.** Full state never leaves the server.
- Discriminating check: if the design ever broadcasts `state` or trusts a client action, it is wrong.

## Reconnect / robustness (advisor minors — load-bearing, not polish)
- Each human seat gets a private **session token**. Disconnect → seat temporarily played by
  a random bot; **reconnect with token → reclaim the seat.**
- Disconnect detection is required (untimed play depends on bot-fallback to avoid a hung game).

## Data flow
`join → lobby → start → [ loop: current seat (human: await WS action | bot: auto) →
validate → engine.step → broadcast per-seat views ] → winner → end.`

## Testing
- **Unit:** per-seat serializer hides every *other* seat's inventory and the shell order
  (assert no foreign inventory / no shell list appears in any produced view).
- **Unit:** server rejects an illegal `action{index}` (state unchanged).
- **Integration:** a full game driven by scripted WS actions + random bots reaches a winner;
  every broadcast view contains only permitted fields.
- Existing engine tests remain unchanged/green.

## Success criteria
Open the public URL from a machine that is **not** the host, enter an invite code, take a
seat; random bots fill to 5; play a **full game to a winner** in-browser, real-time — with
**no client able to see another player's hand or the shell order.**

## Deferred (explicit, so the boundary is clear)
LLM seats (NL state-render + real talk-phase chatroom) · the spec's timed talk→decision
negotiation · timers/timeouts · durable rooms · spectator mode.
