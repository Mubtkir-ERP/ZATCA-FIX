import unittest
from xml.etree import ElementTree as ET

from zatca_fix.xml_patch import CAC_NS, CBC_NS, NS, normalize_xml


XML_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
 <cac:AllowanceCharge><cbc:ChargeIndicator>false</cbc:ChargeIndicator><cbc:Amount currencyID="SAR">0.00</cbc:Amount></cac:AllowanceCharge>
 <cac:TaxTotal><cbc:TaxAmount currencyID="SAR">68.85</cbc:TaxAmount><cac:TaxSubtotal><cbc:TaxableAmount currencyID="SAR">458.97</cbc:TaxableAmount><cbc:TaxAmount currencyID="SAR">68.85</cbc:TaxAmount></cac:TaxSubtotal></cac:TaxTotal>
 <cac:TaxTotal><cbc:TaxAmount currencyID="SAR">68.85</cbc:TaxAmount></cac:TaxTotal>
 <cac:LegalMonetaryTotal>
  <cbc:LineExtensionAmount currencyID="SAR">458.97</cbc:LineExtensionAmount>
  <cbc:TaxExclusiveAmount currencyID="SAR">458.97</cbc:TaxExclusiveAmount>
  <cbc:TaxInclusiveAmount currencyID="SAR">527.81</cbc:TaxInclusiveAmount>
  <cbc:AllowanceTotalAmount currencyID="SAR">0.00</cbc:AllowanceTotalAmount>
  <cbc:PayableAmount currencyID="SAR">527.81</cbc:PayableAmount>
 </cac:LegalMonetaryTotal>
 <cac:InvoiceLine>
  <cbc:ID>1</cbc:ID>
  <cbc:LineExtensionAmount currencyID="SAR">458.97</cbc:LineExtensionAmount>
  <cac:TaxTotal><cbc:TaxAmount currencyID="SAR">68.85</cbc:TaxAmount><cbc:RoundingAmount currencyID="SAR">527.81</cbc:RoundingAmount></cac:TaxTotal>
  <cac:Price><cbc:PriceAmount currencyID="SAR">458.97</cbc:PriceAmount></cac:Price>
 </cac:InvoiceLine>
</Invoice>'''


class XMLPatchTests(unittest.TestCase):
    def test_rounding_and_totals(self):
        fixed, report = normalize_xml(XML_TEMPLATE)
        root = ET.fromstring(fixed)
        legal = root.find('cac:LegalMonetaryTotal', NS)
        self.assertEqual(legal.find('cbc:TaxInclusiveAmount', NS).text, '527.82')
        self.assertEqual(legal.find('cbc:PayableRoundingAmount', NS).text, '-0.01')
        self.assertEqual(legal.find('cbc:PayableAmount', NS).text, '527.81')

        line = root.find('cac:InvoiceLine', NS)
        self.assertEqual(line.find('cac:TaxTotal/cbc:RoundingAmount', NS).text, '527.82')
        self.assertIn('BR-KSA-51', report['rules'])
        self.assertIn('BR-CO-15', report['rules'])
        self.assertIn('BR-CO-16', report['rules'])

    def test_positive_payable_rounding(self):
        xml = XML_TEMPLATE.replace('527.81</cbc:TaxInclusiveAmount>', '527.82</cbc:TaxInclusiveAmount>').replace(
            '527.81</cbc:PayableAmount>', '527.83</cbc:PayableAmount>'
        )
        fixed, _ = normalize_xml(xml)
        root = ET.fromstring(fixed)
        legal = root.find('cac:LegalMonetaryTotal', NS)
        self.assertEqual(legal.find('cbc:PayableRoundingAmount', NS).text, '0.01')

    def test_price_allowance_equation(self):
        xml = XML_TEMPLATE.replace(
            '<cac:Price><cbc:PriceAmount currencyID="SAR">458.97</cbc:PriceAmount></cac:Price>',
            '<cac:Price><cbc:PriceAmount currencyID="SAR">80.00</cbc:PriceAmount>'
            '<cac:AllowanceCharge><cbc:ChargeIndicator>false</cbc:ChargeIndicator>'
            '<cbc:Amount currencyID="SAR">20.00</cbc:Amount>'
            '<cbc:BaseAmount currencyID="SAR">99.99</cbc:BaseAmount></cac:AllowanceCharge></cac:Price>'
        )
        fixed, report = normalize_xml(xml)
        root = ET.fromstring(fixed)
        base = root.find('cac:InvoiceLine/cac:Price/cac:AllowanceCharge/cbc:BaseAmount', NS)
        self.assertEqual(base.text, '100.00')
        self.assertIn('BR-KSA-EN16931-07', report['rules'])


if __name__ == '__main__':
    unittest.main()
