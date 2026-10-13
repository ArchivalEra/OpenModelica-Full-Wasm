# OpenModelica-Full-Wasm

[English](README.md) · [中文](README.zh.md) · [Deutsch](README.de.md)

**OpenModelica** (Modelica-Compiler + Simulationslaufzeit) → **WebAssembly**, läuft im Browser,
**reine Client-Berechnung, kein serverseitiger Ausführungsendpunkt**.

> 🔒 Dieses Repository ist **private**. Schwester-Repository
> [`Octave-Full-Wasm`](https://github.com/ArchivalEra/Octave-Full-Wasm) ist die **gleichrangige**
> andere Hälfte (dort läuft die MATLAB-Syntax-Seite).

---

## Warum es dieses Repository gibt (in einem Satz)

Das MATLAB-Ökosystem hat **drei Achsen**:

| Achse | Was | Wer deckt es ab |
|---|---|---|
| ① | MATLAB-**Sprache** (`.m` / Matrixsemantik) | `Octave-Full-Wasm` |
| ② | **Simulink** (kausale Blockdiagramme) | `Octave-Full-Wasm`-Engine + ein JS-Frontend |
| ③ | **Simscape** (**nicht-kausale physikalische Modellierung**: Elektrik/Fluid/Thermik/Mechanik…) | **dieses Repo** |

Achse ③ kann das Schwester-Repository **von Natur aus nicht** liefern: Octave ist eine
numerische/imperative Sprache und hat die Maschine aus „Symbolik + Indexreduktion + DAE" nicht.
**Gemessener Beleg** (auf der 8761-Seite des Schwester-Repos): Octave löst **index-1 DAE**
(RC-Schaltung `V(5)=0.9931` gegen Theorie `0.9933`), aber **nicht index-3**
(Zwangspendel `IDASolve failed`) — und Indexreduktion ist **genau die Kernarbeit des
OpenModelica-Compilers**. Die zwei Engines sind eine **Staffelübergabe**, keine Doppelung.

## Wie die zwei Engines zusammenspielen (ein `.mat`-Kanal)

```
OpenModelica-Lane: Modellierung auf Gleichungsebene (Symbolik + Indexreduktion + MSL)
                        │  Simulation
                        ▼
                 xxx_res.mat (MAT4)
                        │
Octave-Lane: load → numerisches Lösen + Regelung/Signal/Statistik → Plotten/Analyse
```

Das ist dieselbe Aufteilung wie **„Simscape modelliert, MATLAB analysiert"**, nur mit zwei
wasm-Engines und `.mat` statt gemeinsamem Speicher. Der `.mat`-Handschlag ist **auf beiden
Seiten bereits vorhanden** (OM gibt MAT4 aus; Octave liest/schreibt `.mat`, gemessen).

## Offizieller Weg (kein Drittanbieter-Rezept)

Das **offizielle** OpenModelica-Repository hat ein erstklassiges wasm-Buildziel
(`OMCompiler/Compiler/.cmake/rust_omc.cmake`): `RUST_OMC_WASM_RUNTIME`, `wasm32-wasip1`-Cross-Compile,
`omc.wasm`, Artefakt-Übergabe, `wasm-jit`-Laufzeit.
⇒ **Dieses Repo folgt diesem Weg** — also „Upstream-Submodul + selbst cross-compilieren +
Same-Origin-Hosting", **dieselbe Art Repository wie `Octave-Full-Wasm`**
(Unterschied nur in der Toolchain: hier **Rust + wasm32-wasip1**).

## Drei Linien (eine Linie, eine Architektur)

    master              → Artefakt wasm64, kompiliert nur wasm64
    wasm32              → Artefakt wasm32, kompiliert nur wasm32
    IllegalPerformance  → Performance-Linie (SIMD / Threads / optimierte Bibliotheken)

Kriterium = `python3 build/113/check-lane-purity.py` (Host / Module / linienspezifisches
Site-Verzeichnis — alle drei gleich; falsche Linie wird namentlich gemeldet, rc=1;
Gegenprobe: falsches Artefakt muss rot werden).

**Alle drei Linien sind bereits vorhanden** (`master` / `wasm32` / `IllegalPerformance`, gleicher Basis-Commit) — siehe `git branch -a`.


## Fakten-System (Einfacht, Antihalluzination)

Die **einzige Quelle** für Zahlen ist `build/FACTS.json`; Dokumenttexte **schreiben keine Zahlen
ab**, sondern `[[Schlüssel]]`; neben jeder Tatsache steht ein **Wiederholbefehl**, den die Gates
bei jedem Commit wörtlich ausführen. Jedes Gate muss **beweisen können, dass es rot wird**
(`sh gates-selftest.sh`).

## Dokumentenkarte

| Datei | Inhalt |
|---|---|
| `docs/REQUIREMENTS.md` | **Anforderungsdokument**: was zu tun ist, je Punkt mit Messung + Abnahmekriterium |
| `docs/EINFACHT-INTEGRATION.md` | **Einfacht-Integration** (inkl. 7 gemessener Fallstricke) |
| `docs/FORK-PIPELINE-AND-LESSONS.md` | **Fork-Pipeline + alle Erfahrungen** |
| `maintaince.md` | Richtung und Karte |
| `STATE.md` | Live-Status (+ Maschinenblock am Ende) |
| `AGENTS.md` | Harte Regeln für Agenten |
| `CONTEXT.md` | Glossar (je Begriff eine Definition + ein Wiederholbefehl) |
| `HISTORY.md` | Historie (append-only) |

## Aktueller Stand

**★ Anforderung A ist abgeschlossen** (2026-10-13): Das offizielle wasm-Ziel hat ein Artefakt
gebaut, das unter Node läuft — `OpenModelicaCompiler_bg.wasm` (`omc.build.json`
**verdict=ok**), `node omc-cli.js 'getVersion()'` liefert eine Versionskette.
Toolchain = **clang 24** + quellgleich kompilierte wasm32-builtins + Rust `nightly-2026-05-31`;
Build-Pfad = direkt auf dem Host (Docker ist hier nicht nutzbar).
**Upstream-Pins**: `upstream/openmodelica` = `cbff5eb7…`, `OMCompiler/3rdParty` = `ae7e482a…`.

**Noch nicht gemacht** (nicht verwechseln): Modell Ende-zu-Ende im Browser (Anforderung B)
und `.mat`-Handshake (Anforderung D).
**Nächster Schritt = Anforderung B** (offen, Ticket 03): Node-seitig sind
`loadFile`/`getClassNames`/`translateModel` grün (Compiler-Frontend vollständig, das
Modul-wasm wird wirklich geschrieben); `simulate()` hängt an
`Import #0 "env" "rt_host_lin_solve": function import requires a callable`.
**Ursache gefunden**: der Runtime-Blob im Hand-over ist die **host-delegierende** Variante
(von stage1 nativ gebaut, mit `host_lin_solve`), und stage2 verwendet ihn per Dateiname
wieder. **Der Fix steckt im Build-Skript, ist aber noch nicht verifiziert**
(Neubau wurde vom Herunterfahren unterbrochen). Prüfbefehl:
`node test/node/accept-omc-simulate.mjs`.

⚠️ **Zwei Stellen des Anforderungsdokuments wurden durch Messungen widerlegt**
(dokumentiert in `docs/REQUIREMENTS.md` §7 — der Originaltext wird nicht stillschweigend
geändert): Die von der `master`-Linie geforderte **wasm64-Unterstützung existiert upstream
nicht** ⇒ das erste Artefakt ist **wasm32** (die einzige offiziell unterstützte Variante);
der echte Artefaktname ist **`OpenModelicaCompiler_bg.wasm`** (nicht `omc.wasm`).

## Lizenz

**AGPL-3.0-or-later** (siehe `LICENSE`).
Upstream OpenModelica ist **AGPLv3 / OSMC-PL (Doppellizenz)** — kompatibel mit diesem Repo.
Lizenzen der Upstream-Drittanbieter siehe `THIRD-PARTY-NOTICES.md`.

## 文件清单（自动）

<!-- AUTO:FILES -->
<!-- /AUTO -->
