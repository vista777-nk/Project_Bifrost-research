"""Bounded wrapper around the pinned Electronics Workbench codec."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from lxml import etree

from .xmlio import native_xml_bytes, parse_native_xml


class NativeCodec:
    def __init__(self, home: Path | None = None) -> None:
        self.home = home or Path(
            os.environ.get("BIFROST_AUTHORING_HOME", Path.home() / ".bifrost-authoring")
        )
        self.node = shutil.which("node")
        if (
            not self.node
            or not (self.home / "node" / "node_modules" / "electronics-workbench-decoder").is_dir()
        ):
            raise ValueError(
                "Native authoring codec is not configured; run the authoring setup command."
            )

    def _call(self, mode: str, source: Path, destination: Path) -> None:
        result = subprocess.run(
            [
                self.node,
                str(Path(__file__).with_name("codec.mjs")),
                mode,
                str(source),
                str(destination),
                str(self.home / "node"),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if result.returncode or not destination.is_file():
            raise ValueError(f"Native codec failed: {result.stderr[:1500]}")

    def decode(self, source: Path) -> etree._ElementTree:
        with TemporaryDirectory(prefix="bifrost-native-decode-") as directory:
            xml = Path(directory) / "decoded.xml"
            self._call("decode", source, xml)
            tree = parse_native_xml(xml.read_bytes())
        if tree.getroot().tag != "MSMElectronicsWorkbench" or tree.getroot().get("Schema") != "67":
            raise ValueError("Only the verified Multisim schema 67 is supported.")
        return tree

    def encode(self, tree: etree._ElementTree, output: Path) -> None:
        with TemporaryDirectory(prefix="bifrost-native-encode-") as directory:
            source = Path(directory) / "native.xml"
            source.write_bytes(native_xml_bytes(tree))
            self._call("encode", source, output)
