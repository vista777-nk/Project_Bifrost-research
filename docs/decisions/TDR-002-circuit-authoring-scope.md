# TDR-002: Native Circuit Creation and Editing

Date: 2026-09-08.
Status: User requirement clarified; authoring implementation is not complete.

## Requirement

Bifrost must let Codex **design and edit circuits in both KiCad and Multisim**.
Inspection, export, simulation, and a working MCP connection are supporting
capabilities, not a substitute for circuit authoring or the product's completion
criteria. This corrects the narrower Phase 1 task list, not the user's original goal.

The minimum circuit-authoring scope is native schematic creation and editing.
KiCad PCB placement and routing are a separate capability; PCB-only scripting
must not be presented as schematic authoring.

Required user-visible operations include:

- Create a native design from a circuit specification.
- Find and place real library components with references and parameter values.
- Connect, disconnect, and change pin/net relationships, including real wires.
- Change component values, replace components, move/rotate them, and remove them.
- Save a new native file, reopen it in the target application, and verify the
  persisted components, parameters, connectivity, and layout.
- Validate the design with applicable electrical/design checks and simulation.

Images, connectivity reports, or standalone SPICE decks do not fulfill this
requirement unless the target application contains a genuine, editable native
schematic with the requested components and connections.

## Current State and API Evidence

| Area | Evidence | Remaining Work |
|---|---|---|
| Codex relay | Installed and tested through MCP | Authoring actions and their contracts |
| Multisim inspection/analysis | Live inspection, reports, DC/AC/transient tests pass | These are infrastructure, not authoring acceptance |
| Multisim parameter editing | Installed COM type library exposes `RLCValue`, `CircuitParameterValue`, and `ReplaceComponent` | Implement setters and verify persisted changes after reopening |
| Multisim persistence | `NewFile`, `Save`, and `SaveAs` are exposed | An empty new document is not a newly designed circuit |
| Multisim topology authoring | No direct component-placement or wire-creation method was found on the inspected `IMultisimApp` and `IMultisimCircuit` interfaces | Verify a supported automation/import route for native placement and wiring |
| KiCad PCB editing | KiCad 8 documents the `pcbnew` board-editing API | Implement and test PCB operations separately |
| KiCad schematic editing | KiCad documents its native schematic file format | Select a version-compatible structured authoring path and verify native round trips |

The Multisim evidence is from the installed 14.3 `MSInterface.dll` type library,
queried without modifying a circuit. Exposed editing methods have not yet been
tested as write operations. Absence on those two interfaces does not prove that
all other integration routes are impossible.

KiCad references: [PCB scripting](https://docs.kicad.org/8.0/en/pcbnew/pcbnew.html#scripting)
and [schematic file format](https://dev-docs.kicad.org/en/file-formats/sexpr-schematic/).
Use version-compatible structured APIs/parsers; do not edit schematic syntax
with regex replacements or discard unrecognized document fields.

## Implementation Gates

1. Verify the Multisim route for native component placement and wiring. Test
   any import/template approach for genuinely editable symbols and connections;
   do not silently reduce arbitrary creation to parameter changes in a template.
2. Specify bounded authoring actions, component/pin identity, units, semantic
   previews, output paths, and validation results before changing MCP contracts.
3. Implement a first persisted edit: change an existing R/L/C value, save to a
   new `.ms14` file, reopen it, and verify the value and unchanged source hash.
   This is an incremental editing milestone, not completion of circuit creation.
4. Implement native schematic creation/editing in both applications and pass the
   cross-application acceptance case below.
5. Only then describe the plugin as meeting the circuit-design requirement.

If Multisim authoring requires GUI automation, a new extension, or a software
upgrade, present that requirement explicitly. The existing API-first/no-GUI
constraint remains in effect until the user approves a documented change.

## Acceptance Case

For both applications, Codex must:

1. Create a native 5 V voltage-divider schematic with two 10 kohm resistors,
   named nodes, and real pin-to-pin connections. Reopen it successfully.
2. Change the lower resistor to 20 kohm and save a distinct revision. Reopen
   that revision and verify the persisted value and connectivity.
3. Add a capacitor across the lower resistor, then remove it in another revision.
   Verify the topology changes, not merely a change to a text report.
4. Report electrical checks. In Multisim, verify DC output near 2.5 V before
   the resistor edit and near 3.333 V afterward using actual simulation results.
5. Return native file paths, revision hashes, semantic changes, and validation
   evidence. Preserve pre-existing user files unless overwrite is explicitly approved.

The current test totals do not establish that any of these authoring cases pass.

## Safety

Keep originals immutable by default, but persist approved edits to explicit new
native artifacts. Temporary copies that are discarded after analysis cannot
satisfy an editing request. Validate the saved artifact before publishing it,
preserve unrelated design content, and retain rollback/revision evidence.
Existing overwrite confirmation and race checks must also apply to native files.
