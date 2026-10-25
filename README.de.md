# OpenModelica-Full-Wasm

[![readme-sync](https://img.shields.io/github/actions/workflow/status/ArchivalEra/OpenModelica-Full-Wasm/readme-sync.yml?branch=master&style=flat-square)](https://github.com/ArchivalEra/OpenModelica-Full-Wasm/actions/workflows/readme-sync.yml)
[![facts](https://img.shields.io/github/actions/workflow/status/ArchivalEra/OpenModelica-Full-Wasm/facts.yml?branch=master&style=flat-square)](https://github.com/ArchivalEra/OpenModelica-Full-Wasm/actions/workflows/facts.yml)
[![python](https://img.shields.io/badge/python-3.13%2B-blue?style=flat-square)](.github/workflows/facts.yml)
[![toolchain](https://img.shields.io/badge/clang24%20%2B%20Rust%20nightly-toolchain-informational?style=flat-square)](build/113/provision-toolchain.sh)
[![upstream](https://img.shields.io/badge/OpenModelica-cbff5eb7-informational?style=flat-square)](build/upstream-pins.json)
[![engine](https://img.shields.io/badge/Modelica-engine-orange?style=flat-square)](docs/REQUIREMENTS.md)
[![lane](https://img.shields.io/badge/wasm32-lane-blue?style=flat-square)](STATE.md)
[![COI](https://img.shields.io/badge/COI-not%20required-success?style=flat-square)](STATE.md)
[![facts](https://img.shields.io/badge/Einfacht-powered-purple?style=flat-square)](https://github.com/ArchivalEra/Einfacht)

[English](README.md) · [中文](README.zh.md) · [Deutsch](README.de.md)

OpenModelica (Modelica-Compiler + Simulationslaufzeit), kompiliert zu WebAssembly, läuft im Browser. Reine Client-Berechnung, kein serverseitiger Ausführungsendpunkt.

Schwester-Repository: [Octave-Full-Wasm](https://github.com/ArchivalEra/Octave-Full-Wasm) (die Engine für die MATLAB-Syntax-Seite) · Faktensystem: [Einfacht](https://github.com/ArchivalEra/Einfacht)

## Warum es dieses Repository gibt

Das MATLAB-Ökosystem hat drei Achsen:

| Achse | Was | Wer deckt es ab |
|---|---|---|
| ① | MATLAB-Sprache (`.m` / Matrixsemantik) | Octave-Full-Wasm |
| ② | Simulink (kausale Blockdiagramme) | Octave-Full-Wasm-Engine + ein JS-Frontend |
| ③ | Simscape (nicht-kausale physikalische Modellierung: Elektrik/Fluid/Thermik/Mechanik…) | dieses Repo |

Achse ③ kann das Schwester-Repository von Natur aus nicht liefern: Octave ist eine numerische/imperative Sprache und hat die Maschine aus „Symbolik + Indexreduktion + DAE" nicht. Gemessen (auf der Seite des Schwester-Repos): Octave löst index-1 DAE (RC-Schaltung `V(5)=0.9931` gegen Theorie `0.9933`), aber nicht index-3 (Zwangspendel `IDASolve failed`) — und Indexreduktion ist genau die Kernarbeit des OpenModelica-Compilers. Die zwei Engines sind eine Staffelübergabe, keine Doppelung.

## Wie die zwei Engines zusammenspielen (ein `.mat`-Kanal)

```
OpenModelica-Lane: Modellierung auf Gleichungsebene (Symbolik + Indexreduktion + MSL)
                        │ Simulation
                        ▼
                 xxx_res.mat (MAT4)
                        │
Octave-Lane: load → numerisches Lösen + Regelung/Signal/Statistik → Plotten/Analyse
```

Das ist dieselbe Aufteilung wie „Simscape modelliert, MATLAB analysiert", nur mit zwei wasm-Engines und `.mat` als Kanal (OM gibt MAT4 aus; Octave liest/schreibt `.mat`, gemessen).

## Offizieller Weg

Das offizielle OpenModelica-Repository hat ein erstklassiges wasm-Buildziel (`OMCompiler/Compiler/.cmake/rust_omc.cmake`). Dieses Repo folgt diesem Weg: Upstream-Submodul + selbst cross-compilieren + Same-Origin-Hosting. Toolchain: Rust + wasm32-wasip1 (das Schwester-Repo nutzt emsdk; keine gegenseitigen Submodule).

## Zwei Linien (eine Linie, eine Architektur)

```
master              → Artefakt wasm64 (Upstream hat keinen Pfad; vorerst wasm32-Artefakt)
wasm32              → Artefakt wasm32, kompiliert nur wasm32
```

Kriterium: `python3 build/113/check-lane-purity.py` (Host / Module / linienspezifisches Site-Verzeichnis — alle drei gleich; falsche Linie wird namentlich gemeldet, die Gegenprobe muss rot werden).

Die Performance-Linie IllegalPerformance wurde auf Anweisung des Nutzers gelöscht (2026-10-14): Erst wenn wasm64 über die offizielle Fork-Pipeline produktionsreif ist, lohnt sich Entwicklung abseits des Upstream-Baums; die alten Objekte hängen am Tag `archive/ilperf-f283610`, nach wasm64-Produktionsreife wird die Linie neu aufgebaut. Beide Linien sind inhaltlich synchron, `git diff master wasm32 --stat` muss leer sein.

Aktuelle Veröffentlichung: v0.1.0-wasm32 (Versionsidentität `build/VERSION.json`, Release-Notizen `docs/RELEASE-v0.1.0-wasm32.md`).

## Stand

Jede Anforderung hat ein wiederholbares Abnahmekriterium, alles aktuell grün (Einzelheiten in `HISTORY.md` und `.scratch/open-questions/issues/`):

| Anforderung | Kriterium | Ergebnis |
|---|---|---|
| A Offizielles wasm-Ziel baut ein Artefakt | `bash build/113/build-omc-wasm.sh --verify` | verdict=ok |
| B Modell im Browser durchlaufen | `sh test/browser/run-omc-page.sh` | 10 PASS / 0 FAIL |
| C Zwei Linien + Architektur-Reinheit | `python3 build/113/check-lane-purity.py --selftest` | 24 PASS / 0 fail |
| D `.mat`-Handshake mit Octave | `sh test/browser/run-mat-handshake.sh` | 14 PASS / 0 FAIL |
| E MATLAB-Semantikbrücke `omc_*` | `sh test/browser/run-omc-bridge.sh` | 11 PASS / 0 FAIL |
| Gleiche Seite (zwei Engines, eine Seite) | `sh test/browser/run-samepage.sh` | 8 PASS / 0 FAIL |
| MSL-Anlage vor Ort (Offline-Bibliothek, mail/016) | `site/msl-local.html` (Site 8765) | MSL-LOCAL PASS |
| Export FMU (extern gefundener Defekt, behoben) | `sh test/browser/run-export-fmu.sh` | 6 PASS / 0 FAIL |

- Artefakt: Web-Variante 74,6 MB (nach `-Oz`, sha im Ledger `omc_web_wasm_sha`); kein COI nötig (0 Atomar-Befehle / 0 Thread-Imports, ein gewöhnlicher http.server genügt).
- Die alte Aussage „gleiche Seite nicht machbar" ist widerlegt (Messfehler, siehe `build/retractions.json`); die Wurzel des Export-FMU-Defekts: unser clang24 ist neuer als der Upstream-CI-clang und schreibt die `dylink.0`-Subsection 6, die der FMU-Linker nicht kennt — Fix = `build/113/strip-dylink-features.py`, in die Build-Kette eingebaut.
- Die Grenze von wasm64: auf der Toolchain-Seite machbar (`build/113/build-w64-spike.sh`, baut in 8,8 s), es fehlt nur der Upstream-CMake-Pfad (`rust_omc.cmake` 0 Treffer für wasm64) — wir warten auf den Upstream, es ist nicht „nicht baubar".
- Nächster Schritt: Anforderung F (Octave-UI-Integration).

## Fakten-System

Die einzige Quelle für Zahlen ist `build/FACTS.json`; Dokumenttexte schreiben keine Zahlen ab, sondern `[[Schlüssel]]`; neben jeder Tatsache steht ein Wiederholbefehl, den die Gates bei jedem Commit wörtlich ausführen; jedes Gate muss beweisen können, dass es rot wird (`sh gates-selftest.sh`). Eine Lehre aus der Praxis: schwankende Messgrößen (JS-Heap, Laufzeit) dürfen nicht mit ihrem Rohwert ins Ledger — sie bekommen eine Größenklasse, die gröber als das Rauschen ist, und `cmd` rundet identisch, damit der wörtliche Wiederhollauf stabil bleibt.

## Dokumentenkarte

| Datei | Inhalt |
|---|---|
| `docs/REQUIREMENTS.md` | Anforderungsdokument: was zu tun ist, je Punkt mit Messung + Abnahmekriterium |
| `docs/EINFACHT-INTEGRATION.md` | Einfacht-Integration (inkl. 7 gemessener Fallstricke) |
| `docs/FORK-PIPELINE-AND-LESSONS.md` | Fork-Pipeline + alle Erfahrungen |
| `docs/LANES-AND-MEMORY-MODEL.md` | Speichermodell- & Linien-Erfahrung (drei echte Mischunfaelle, Kriterien des Reinheits-Gates) |
| `maintaince.md` | Richtung und Karte |
| `STATE.md` | Live-Status (Maschinenblock am Ende, aus dem Ledger gerendert) |
| `AGENTS.md` | Harte Regeln für Agenten |
| `CONTEXT.md` | Glossar |
| `HISTORY.md` | Historie (append-only) |
| `mail/` | Posteingang für Cross-Agent-Kommunikation (Vier-Repo-Cluster; Regeln in `mail/README.md`) |

## Lizenz

AGPL-3.0-or-later (siehe `LICENSE`). Upstream OpenModelica ist AGPLv3 / OSMC-PL (Doppellizenz), kompatibel mit diesem Repo; Lizenzen der Upstream-Drittanbieter siehe `THIRD-PARTY-NOTICES.md`.
