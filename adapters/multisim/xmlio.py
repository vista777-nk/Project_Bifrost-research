"""Preserve native attribute whitespace across a standards-compliant XML parser.

Multisim stores SPICE line breaks literally inside XML attributes. XML 1.0
normalizes those characters to spaces, so the native codec must protect and
restore them at the lexical boundary. All semantic editing still uses lxml.
"""

from __future__ import annotations

import io

from lxml import etree

_ESCAPES = {9: b"&#9;", 10: b"&#10;", 13: b"&#13;"}


def attribute_whitespace(data: bytes, *, restore: bool = False) -> bytes:
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Native XML exceeds 64 MiB.")
    output = bytearray()
    index, quote = 0, None
    in_tag = False
    while index < len(data):
        if not in_tag:
            terminator = None
            if data.startswith(b"<!--", index):
                terminator = b"-->"
            elif data.startswith(b"<![CDATA[", index):
                terminator = b"]]>"
            elif data.startswith(b"<?", index):
                terminator = b"?>"
            elif data[index : index + 9].upper() == b"<!DOCTYPE":
                raise ValueError("DTDs are not accepted in native authoring XML.")
            if terminator:
                end = data.find(terminator, index)
                if end < 0:
                    raise ValueError("Unterminated XML declaration.")
                end += len(terminator)
                output.extend(data[index:end])
                index = end
                continue
            if data[index] == 60:
                in_tag = True
        elif quote is not None:
            if data[index] == quote:
                quote = None
            elif not restore and data[index] in _ESCAPES:
                output.extend(_ESCAPES[data[index]])
                index += 1
                continue
            elif restore and data[index] == 38:
                matched = False
                for character, escaped in _ESCAPES.items():
                    if data.startswith(escaped, index):
                        output.append(character)
                        index += len(escaped)
                        matched = True
                        break
                if matched:
                    continue
        elif data[index] in (34, 39):
            quote = data[index]
        elif data[index] == 62:
            in_tag = False
        output.append(data[index])
        index += 1
    return bytes(output)


def parse_native_xml(data: bytes) -> etree._ElementTree:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, strip_cdata=False)
    return etree.parse(io.BytesIO(attribute_whitespace(data)), parser)


def native_xml_bytes(tree: etree._ElementTree) -> bytes:
    return attribute_whitespace(
        etree.tostring(tree, encoding="ASCII", xml_declaration=True), restore=True
    )
