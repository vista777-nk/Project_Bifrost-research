"""Native identity and transform tests use original synthetic fixtures."""

from lxml import etree

from adapters.multisim.schematic import pin_info
from adapters.multisim.xmlio import native_xml_bytes, parse_native_xml


def test_electrical_port_id_does_not_depend_on_a_displayed_pin_number():
    symbol = etree.fromstring(b"""<CIITSymbolComp Transformer-M20="100" Transformer-M21="200">
      <Objects><Item><CIITPinSymbolComp PortID="electrical-port" Transformer-M20="10">
        <Objects><Item ID="connector"><CIITPinConnectorComp ptCenterX="3" ptCenterY="4"
          Transformer-M00="-1" Transformer-M11="-1"/></Item></Objects>
      </CIITPinSymbolComp></Item></Objects></CIITSymbolComp>""")
    pins = pin_info(symbol, port_names={"electrical-port": "1"})
    assert pins["1"]["point"] == (107, 196)
    assert pins["1"]["connector_id"] == "connector"
    local = pin_info(symbol, False, {"electrical-port": "1"})
    assert local["1"]["point"] == (7, -4)


def test_native_spice_attribute_line_breaks_survive_semantic_edits():
    raw = (
        b'<MSMElectronicsWorkbench Schema="67"><Model '
        b'String="R1 1 0 1000\n.model R R( )\r\t.end"/><Item/><Item/>'
        b"</MSMElectronicsWorkbench>"
    )
    tree = parse_native_xml(raw)
    expected = "R1 1 0 1000\n.model R R( )\r\t.end"
    assert tree.getroot().find("Model").get("String") == expected
    encoded = native_xml_bytes(tree)
    assert b"1000\n.model" in encoded
    assert parse_native_xml(encoded).getroot().find("Model").get("String") == expected
    assert len(tree.getroot().findall("Item")) == 2


def test_native_whitespace_codec_does_not_rewrite_comments_or_cdata():
    raw = (
        b'<MSMElectronicsWorkbench Schema="67"><!-- a="x\ny" -->'
        b'<Data><![CDATA[a="x\ny"]]></Data><Value Text="&amp;#10;"/>'
        b"</MSMElectronicsWorkbench>"
    )
    encoded = native_xml_bytes(parse_native_xml(raw))
    assert b'<!-- a="x\ny" -->' in encoded
    assert b'<![CDATA[a="x\ny"]]>' in encoded
    assert parse_native_xml(encoded).getroot().find("Value").get("Text") == "&#10;"
