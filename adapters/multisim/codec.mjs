import { createRequire } from "node:module";
import { resolve } from "node:path";
import { readFileSync, statSync, writeFileSync } from "node:fs";

try {
  const [mode, input, output, packageRoot] = process.argv.slice(2);
  if (!["decode", "encode"].includes(mode)) throw new Error("Invalid codec operation");
  if (statSync(input).size > 32 * 1024 * 1024) throw new Error("Native input exceeds 32 MiB");
  const source = readFileSync(input);
  const require = createRequire(resolve(packageRoot, "package.json"));
  const { decodeBuffer, encodeBuffer, formatByKey } = require("electronics-workbench-decoder");
  let result;
  if (mode === "decode") {
    const signature = Buffer.from("MSMCompressedElectronicsWorkbenchXML");
    if (source.length < 44 || !source.subarray(0, signature.length).equals(signature)) {
      throw new Error("Unsupported Multisim container");
    }
    if (source.readBigUInt64LE(signature.length) > 64n * 1024n * 1024n) {
      throw new Error("Decoded native document exceeds 64 MiB");
    }
    result = Buffer.from(decodeBuffer(source).xml);
  } else {
    result = Buffer.from(encodeBuffer(source, formatByKey("multisim")));
    if (!Buffer.from(decodeBuffer(result).xml).equals(source)) throw new Error("Codec round trip failed");
  }
  writeFileSync(output, result, { flag: "wx" });
  console.log(JSON.stringify({ success: true, bytes: result.length }));
} catch (error) {
  console.error(String(error));
  process.exitCode = 1;
}
