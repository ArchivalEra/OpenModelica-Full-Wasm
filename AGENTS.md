# AGENTS.md - OpenModelica-Full-Wasm

Read before working here: `maintaince.md` (direction and map), `STATE.md` (live state,
machine block at the end), `docs/REQUIREMENTS.md` (requirements, each with an
acceptance criterion). Glossary: `CONTEXT.md`.

## Paths

- This repo: `/mnt/hdd/zcode-projects/OpenModelica-Full-Wasm` (private).
- Sister repo (read-only, never modify): `/mnt/hdd/zcode-projects/Octave-Full-Wasm`.
- Upstream source/build tree: `/mnt/hdd/openmodelica-wasm-build/`.
- Never touch `/mnt/hdd/zcode-projects/GONGCHENGSHUXUE20260917`.

## Hard rules

1. Client-side only: OpenModelica always runs as wasm in the browser - no endpoint may
   execute code server-side.
2. Never force-push, delete git objects, rewrite history, or use `--no-verify`.
3. Whitelist repo: any new file needs a matching `!path` entry in `.gitignore` or
   pre-commit rejects it. Do not put `#` comments at the end of `.gitignore` lines  - 
   the comment becomes part of the value (this has bitten three times).

## Push discipline (owner-ruled; per-repo enablement, default off)

Push is per-repo enabled by the owner, default off. Absent an explicit enablement
notice for this repo, do not push: edit locally, commit locally, and put the change
description in your final output - the owner lands it.

When a push is enabled for this repo:

1. The push request and review conclusion do **not** go through `wo-u` (wo-u carries
   task dispatch and rulings only). Write the change description plus your
   `code-review` conclusion into the **final output of your session** - and into the
   commit message - then stop output. The owner reads session outputs and replies with
   consent; push only after that reply.
2. The write channel is the SSH SK key through the akr FIDO2 agent (phone MFA prompt;
   the owner taps Allow). The gh tokens are read-only - HTTPS push returns 403. Do
   not experiment with the channel; a trial push is a violation.
3. A push whose commit message lacks the review conclusion and change description is
   ignored, not retried.
4. Mechanics for this repo (remote is already split):
   - fetch = `https://github.com/ArchivalEra/OpenModelica-Full-Wasm.git` (read-only
     PAT via gh keyring, silent); push =
     `ssh://git@github-ArchivalEra/ArchivalEra/OpenModelica-Full-Wasm.git`
     (`IdentitiesOnly yes`, `~/.ssh/archivalera-main.pub`, port 443 via
     `ProxyCommand socat - PROXY:127.0.0.1:%h:%p,proxyport=2080`).
   - Any `ssh://` URL used for fetch triggers a phone MFA prompt - forbidden. Reads
     go through the `gh` CLI (`gh repo sync` is 403 under a read-only PAT - do not
     use it); plain `git fetch` over the HTTPS URL is the fallback.
   - Proxies: `export https_proxy=http://127.0.0.1:2080 http_proxy=http://127.0.0.1:2080`.
   - Knobs: `set -a; . ./Einfacht.env; set +a` before pushing - pre-push runs the
     local gates, and the three-language README set (`REFLECT_READMES`) is
     conditional: touching any of the three requires all three in the same push.
   - Run the gates under "Before committing" first.

## What this repo is

Sister repo `Octave-Full-Wasm` covers axis 1 (MATLAB language) and 2) (Simulink causal
block diagrams). This repo covers axis 3: Simscape-style non-causal physical modeling  - 
Modelica language, symbolic processing, index reduction, cross-domain MSL libraries.

The two repos are peers and must not reference each other: different toolchains
(sister: emsdk; here: Rust + wasm32-wasip1), so no cross-submodules. Mixed builds are a
known failure mode. Integration happens in `Octave-UI` via a `.mat` handshake.

## Lanes (one lane, one architecture)

```
master   -> wasm64 artifacts (upstream has no wasm64 path yet; currently emits wasm32)
wasm32   -> wasm32 artifacts only
```

Executable criterion:
`python3 build/113/check-lane-purity.py --lane <lane> --host <wasm> --mod <dir...>`
(host 1, lane modules 2, the site lane-specific directory 3; mismatches are named, rc=1).
Rationale: mixed builds succeed on both sides, pass all self-checks, and only fail at
runtime - the criterion must be executable, not eyeballed.

The performance lane (`IllegalPerformance`) was deleted by user order; rebuild it only
after wasm64 reaches production grade via the official fork pipeline.

## Acceptance floor

The dev site is always the last build that passed browser testing. A failed experiment
must not regress it: discard the lane directory, record it, move on.

A deployment candidate must pass the full suite (`PROBES=1`), not just smoke tests  - 
a smoke-only batch once failed the full suite elsewhere.

## Fact discipline (every "this is currently true" needs a re-runnable command)

1. Numbers/behavior come only from measurement, with the reproducing command written
   next to the assertion; otherwise it is history, not status.
2. Move criteria into code, not hand-copied commands in docs; a flag that is assigned
   but never read silently fails - flag changes need a self-check that reads from the
   artifact.
3. "It compiles" != "it works": anything touching runtime behavior must be tested in the
   browser.
4. Assertions must be falsifiable: every new contract ships with at least one negative
   assertion; when behavior changes, flip the assertion (edit the test, not the checker).
5. Assertions have lifecycles: measured (live state) / inferred (NOTES + closing
   experiment) / retracted (`build/retractions.json`).

## Batch closeout (fixed steps)

1. Preflight: run the environment check (`doctor`); if it fails, do not start.
2. The dev site changes only through the governed entry points (`build/promote-*.sh`,
   each with `--dry-run` / `--verify` / `--selftest` and a no-extra-changes negative
   assertion). Experiments write to separate site directories only.
3. Serving: the wasm multithreading tier requires COI headers
   (`Cross-Origin-Opener-Policy: same-origin` +
   `Cross-Origin-Embedder-Policy: require-corp`). Plain `python3 -m http.server` cannot
   send them, and the threaded tier then silently falls back to the base tier.
4. Three-layer SHA (disk / HTTP / page-instantiated) must all be green - "rebuilt the
   program but served the old artifact" is a repeated pitfall.
5. Full regression (`PROBES=1`) -> three-way consistency (dev site / production site /
   repo mirror `--strict`) -> gates -> commit -> (push is executed by the owner, see
   push-path section).

## Before committing

```bash
# Platform layer (Einfacht; source the env carrier first: set -a; . ./Einfacht.env; set +a)
python3 zreflect/facts.py --render-doc STATE.md --check
python3 zreflect/registry.py --run commit
sh gates-selftest.sh
# Repo-specific layer
python3 .githooks/check-whitelist.py
python3 .githooks/witness-upstream-pin.py
python3 zreflect/check_facts_replay.py
python3 build/113/check-lane-purity.py --selftest
sh build/gates-selftest.sh
```

Gate self-tests: every gate must ship `--selftest` with three case classes
(normal passes / must-fail cases actually fail / empty input reports). Every new
repo-specific gate must be registered in `build/gates-selftest.sh` - an unregistered
gate is an unwatched gate. Machine summary line format: `=== N PASS / M fail ===`
(lowercase `fail`).

`check-whitelist.py` only sees staged files; after adding a directory, check
`git status --short --ignored <dir>` yourself.

## Operational pitfalls (measured; do not repeat)

- Never use `sleep` (user-ordered, any form). Run long tasks with
  `run_in_background: true` and wait for the completion notification; follow a live
  process with `tail -f --pid=<pid>`. Never re-run an already-backgrounded task.
- Start heavy work with `setsid nohup ... &`, read its output only via `tail -n`/`grep`;
  do not run other heavy work in parallel with acceptance runs.
- Run test cases from their original repo paths; do not copy them into a harness.
- Verify artifact SHA (three layers) before running tests.
- Build scripts inside a container are a separate copy; sync repo changes into the
  container before running them.
- Never guess mount points, versions, paths, or flags - read them from artifacts or
  config.
- Self-probes must not run on page boot: a bad artifact hangs the whole page. Trigger
  probes on demand, with a timeout.
- Shell traps: `pkill -f 'x'` matches itself (use `'x[y]'`); `rc=$?` after a pipe takes
  the last command's status; `&&` before `&` backgrounds the whole chain; backticks in
  `echo` are command substitution; `grep -c` exits 1 on zero matches; character classes
  in regexes must include digits if digits are expected.
- Conclusions come only from artifacts (`sha256sum`, log directories, probe output),
  never from impressions.

## Agent skills

### Issue tracker
Issues are markdown files in `.scratch/open-questions/issues/NN-*.md` (local tracker).
Each carries a runnable settling command in a `**Settling:**` header line. See
`docs/agents/issue-tracker.md`.

### Triage labels
Five canonical roles written as a `**Status:**` header line (`needs-triage` /
`needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`). `wontfix` is not
deletion. See `docs/agents/triage-labels.md`.

### Domain docs
Single context: root `CONTEXT.md`. See `docs/agents/domain.md`.
