# Non-GUI Circuit Authoring Research

Date: 2026-09-08.
Status: A non-GUI native-file route is verified at prototype level. Public
authoring tools and full TDR-002 acceptance remain unfinished.

## Constraint

The user explicitly rejected mouse/keyboard control. Do not add screen-coordinate
clicking, UI Automation, synthetic input, or an equivalent GUI-control fallback.
Starting the application through COM for native loading, simulation, and image
export is not desktop input control and remains part of the verification path.

The previous recommendation to add a GUI backend was premature. Failure of the
COM `.cir` import path is not evidence that native-file authoring is impossible.

## Verified Non-GUI Alternative

Multisim's `.ms14` is a compressed XML container, not an opaque structure that
can only be written by the GUI. The vendor sample begins with
`MSMCompressedElectronicsWorkbenchXML`; its decoded root is
`MSMElectronicsWorkbench` with schema `67`.

The existing `electronics-workbench-decoder` package provides decoding and
encoding through a library API. The investigated version is `0.2.0`, ISC
licensed. It was installed only under `output/native-format-tools`, with
install scripts disabled and TLS verification enabled. No global package or
security settings were changed.

Recommended architecture:

```text
Validated circuit/edit specification
  -> version-aware native XML object-graph editor
  -> existing compressed-container encoder
  -> new .ms14 artifact
  -> Multisim COM reopen, parameter/connectivity checks, simulation, image export
```

This is native file interoperability, not mouse/keyboard control, a screenshot
substitute, or an Arbitrary SPICE Block.

## Local Proofs

### Container Round Trip

- Decoded NI's Using Analyses sample to 1,884,075 XML bytes.
- Re-encoded it, then decoded again: XML bytes were identical.
- Multisim 14.3 reopened the resulting `.ms14` through the existing MCP/COM
  path and enumerated the original 18 components and two outputs.

### Persisted Native Edit

- Used a structured XML parser to change R2 from 3980 to 20000 ohms in a new copy.
- Preserved all 14,770 XML object records and unrelated document content.
- Re-encoded to a new native file and opened it through COM.
- Multisim's own `RLCValue` returned 20000 for R2; its exported schematic image
  also showed the new value. COM did not perform the edit.

### Native Creation and Connectivity

- Reviewed an external MIT-licensed native XML generator at revision
  `c947c818c634b235f84a95a1584d35646bc338c2`.
- Created an empty version-matched native file through COM and derived a
  local-only R/C/V/ground component pack from the licensed installation.
- Generated and encoded a new divider. Multisim enumerated `R1`, `R2`, and `V1`.
- Generated a second native design with C1. Multisim enumerated `C1`, `R1`,
  `R2`, and `V1`, and its connectivity report placed C1 across R2's two nets.
- Exported both actual schematic images through COM, without controlling input devices.

These creation proofs expose remaining defects in the reference generator:
the selected voltage-source template retained AC-source presentation, and some
wire drawings did not align visually with the symbol pins. Therefore these are
evidence that the file route can create native objects and connections, not
passing 5 V DC-divider or complete layout acceptance tests. Do not adopt the
reference implementation without correcting and validating those issues.

### Source Preservation

The source SHA-256 hashes remained unchanged:

- Using Analyses: `478be136e07434fc662536a6eade21f0e77e05c67d6d03488f879facfa52dd6c`.
- RLC Values: `3d1131432859329eae8dd0c3f38d9edd0b540536811d17693fa146852af85b75`.
- LowPassFilter: `b68b7b0725e70d9a44788b73812e5a4f18f371a078fba6d85e5ad218d1b66218`.

## Other Routes Assessed

- **COM editing:** `RLCValue`, `CircuitParameterValue`, `ReplaceComponent`, and
  `SaveAs` are exposed. They remain useful alongside the native-file editor,
  but do not supply general placement/wiring operations by themselves.
- **COM `.cir` import:** the isolated probe connected, then terminated at
  `OpenFile(.cir)` with exit code `0xC0000409`. It is not a supported plugin route.
- **OECL:** describes component libraries, symbols, packages, and models. It
  can help build a component catalog, but does not itself provide whole-circuit
  editing or solve native wire/layout authoring.
- **Simulator command language:** supports simulation workflows; it must not
  be confused with an editable native schematic object graph.
- **KiCad:** its schematic format documents symbols, pins, wires, coordinates,
  and identities. Use a version-compatible structured parser/editor and native
  validation; `pcbnew` board editing is a separate capability.

## Next Implementation Work

1. Add a bounded, version-aware codec wrapper using the existing library rather
   than inventing a new compressor. Reject unsupported headers/schemas and limit sizes.
2. Implement semantic edits to native component, pin, net, wire, and transform
   records. Preserve object identity, empty positional slots, and unknown content.
3. Derive local library definitions with correct model semantics and full
   symbol/pin transforms. Do not reuse an AC carrier for a DC source silently.
4. Verify both electrical connectivity and visible wire-to-pin geometry after
   reopening. Component counts alone are not sufficient.
5. Add native revision outputs, overwrite guards, semantic previews, and
   rollback evidence; run the entire TDR-002 acceptance case before release.

No authoring functionality has been installed into the public plugin by these
research probes. The format is proprietary and the codec is third-party, not
an NI-supported write API; version-locked tests and fail-closed validation are
required. Templates, decoded vendor XML, vendor-derived images, and generated
vendor-derived designs stay local under ignored `output/` and must not be
redistributed without permission.

## Reproduction Files

- `scripts/probe_multisim_xml.mjs`: bounded file round trips and encoding with
  explicit new output paths; never invokes the decoder's in-place CLI behavior.
- `scripts/probe_multisim_xml_edit.py`: narrow structured R2-value edit proof.
- `scripts/inspect_multisim_native.ps1`: COM-only native inspection and image export.
- `scripts/probe_multisim_native_builder.py`: supervised use of the reviewed
  external generator and local component pack; not a production backend.
- `scripts/probe_multisim_authoring.ps1`: historical failing `.cir` import probe;
  do not run it as an automatic retry or expose it through MCP.
- `output/multisim-xml-probe/` and `output/multisim-native-builder-proof/`: local evidence.

## Primary Sources

- [Electronics Workbench decoder/encoder](https://github.com/cinderblock/electronics-workbench-decoder/).
- [Independent compressed-container converter](https://gist.github.com/barncastle/4277ac44aa47bf8c4389c7df0d160e56).
- [Native Multisim schematic builder](https://github.com/yxy050208/multisim-mcp/blob/main/mcp_server/multisim_mcp/schematic_builder.py).
- [OECL introduction by its developer](https://www.garretfick.com/blog/oecl-intro).
- [KiCad schematic file-format documentation](https://dev-docs.kicad.org/en/file-formats/sexpr-schematic/).
