// Non-GUI interoperability probe; writes only explicitly named, new output files.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: {
    input: { type: "string" },
    output: { type: "string" },
    "codec-root": { type: "string" },
    mode: { type: "string", default: "roundtrip" },
  },
});
assert(values.input && values.output && values["codec-root"], "Specify input, output, and codec-root.");
assert(["roundtrip", "encode"].includes(values.mode), "Unknown mode.");
const input = resolve(values.input);
const output = resolve(values.output);
assert(input !== output && !existsSync(output), "Never overwrite input or an existing output.");
assert(statSync(input).size <= 64 * 1024 * 1024, "Probe input exceeds 64 MiB.");
const require = createRequire(resolve(values["codec-root"], "package.json"));
const { decodeBuffer, encodeBuffer, formatByKey } = require("electronics-workbench-decoder");
const digest = (buffer) => createHash("sha256").update(buffer).digest("hex");
const source = readFileSync(input);
const xml = values.mode === "roundtrip" ? Buffer.from(decodeBuffer(source).xml) : source;
assert(xml.length <= 64 * 1024 * 1024, "Decoded XML exceeds 64 MiB.");
const encoded = Buffer.from(encodeBuffer(xml, formatByKey("multisim")));
const decodedAgain = Buffer.from(decodeBuffer(encoded).xml);
assert(xml.equals(decodedAgain), "The codec did not preserve the XML bytes.");
assert(digest(source) === digest(readFileSync(input)), "Source file changed.");
const sidecar = `${output}.xml`;
assert(!existsSync(sidecar), "Never overwrite an existing XML sidecar.");
mkdirSync(dirname(output), { recursive: true });
writeFileSync(sidecar, xml, { flag: "wx" });
writeFileSync(output, encoded, { flag: "wx" });
console.log(JSON.stringify({
  success: true,
  mode: values.mode,
  input,
  output,
  xml: sidecar,
  source_sha256: digest(source),
  output_sha256: digest(encoded),
  xml_sha256: digest(xml),
  xml_bytes: xml.length,
  output_bytes: encoded.length,
  exact_xml_roundtrip: true,
}, null, 2));
