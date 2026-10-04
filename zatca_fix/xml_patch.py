from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from xml.etree import ElementTree as ET

UBL_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CAC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
EXT_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"

NS = {"ubl": UBL_NS, "cac": CAC_NS, "cbc": CBC_NS, "ext": EXT_NS}
MONEY = Decimal("0.01")
DEFAULT_MAX_PAYABLE_ROUNDING = Decimal("1.00")

ET.register_namespace("", UBL_NS)
ET.register_namespace("cac", CAC_NS)
ET.register_namespace("cbc", CBC_NS)
ET.register_namespace("ext", EXT_NS)


def _q(value: Any) -> Decimal:
    if value in (None, ""):
        value = 0
    try:
        return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def _money_text(value: Decimal) -> str:
    return f"{_q(value):.2f}"


def _text_money(element: ET.Element | None) -> Decimal:
    if element is None:
        return Decimal("0.00")
    return _q(element.text)


def _set_money(element: ET.Element | None, value: Decimal, report: dict, label: str) -> None:
    if element is None:
        return
    old = _text_money(element)
    new = _q(value)
    if old != new:
        report["changes"].append({"field": label, "old": _money_text(old), "new": _money_text(new)})
        element.text = _money_text(new)
    elif element.text != _money_text(new):
        # Normalize representation (e.g. 0.0 -> 0.00) without counting it as a semantic change.
        element.text = _money_text(new)


def _direct_children(parent: ET.Element, namespace: str, tag: str) -> list[ET.Element]:
    return parent.findall(f"{{{namespace}}}{tag}")


def _find(parent: ET.Element | None, path: str) -> ET.Element | None:
    if parent is None:
        return None
    return parent.find(path, NS)


def normalize_xml(
    xml_text: str,
    max_payable_rounding: Decimal | float | str = DEFAULT_MAX_PAYABLE_ROUNDING,
) -> tuple[str, dict]:
    """Normalize RUKN-generated unsigned UBL XML before it is signed.

    The function intentionally changes only derived XML arithmetic fields. It does not
    modify ERPNext accounting values, taxes, GL entries, or submitted Sales Invoices.

    Covered validation relationships:
      * BR-KSA-51: line amount with VAT = line net amount + line VAT amount
      * BR-KSA-EN16931-07: net item price = gross item price - price allowance
      * BR-CO-10: invoice line extension total = sum of invoice line net amounts
      * BR-CO-11: invoice allowance total = sum of document-level allowances
      * BR-CO-14: invoice VAT total = sum of VAT category tax amounts
      * BR-CO-15: tax inclusive amount = tax exclusive amount + invoice VAT amount
      * BR-CO-16: amount due = tax inclusive - prepaid + payable rounding
    """

    report = {
        "changed": False,
        "changes": [],
        "warnings": [],
        "rules": [],
    }

    if not xml_text or "<Invoice" not in xml_text:
        report["warnings"].append("Input does not look like a UBL Invoice XML document.")
        return xml_text, report

    had_declaration = xml_text.lstrip().startswith("<?xml")
    root = ET.fromstring(xml_text)

    # 1) Normalize every invoice line using the values that will actually appear in XML.
    line_extension_sum = Decimal("0.00")
    line_nodes = _direct_children(root, CAC_NS, "InvoiceLine")

    for line in line_nodes:
        line_id = (_find(line, "cbc:ID").text if _find(line, "cbc:ID") is not None else "?")
        line_extension = _find(line, "cbc:LineExtensionAmount")
        line_net = _text_money(line_extension)
        _set_money(line_extension, line_net, report, f"InvoiceLine[{line_id}].LineExtensionAmount")
        line_extension_sum += line_net

        line_tax_total = _find(line, "cac:TaxTotal")
        line_tax = _text_money(_find(line_tax_total, "cbc:TaxAmount"))
        rounding_amount = _find(line_tax_total, "cbc:RoundingAmount")
        if rounding_amount is not None:
            expected_line_with_vat = _q(line_net + line_tax)
            before_count = len(report["changes"])
            _set_money(
                rounding_amount,
                expected_line_with_vat,
                report,
                f"InvoiceLine[{line_id}].RoundingAmount",
            )
            if len(report["changes"]) > before_count and "BR-KSA-51" not in report["rules"]:
                report["rules"].append("BR-KSA-51")

        # Price-level allowance arithmetic (BT-146 = BT-148 - BT-147).
        price = _find(line, "cac:Price")
        if price is not None:
            price_amount_el = _find(price, "cbc:PriceAmount")
            price_amount = _text_money(price_amount_el)
            _set_money(price_amount_el, price_amount, report, f"InvoiceLine[{line_id}].PriceAmount")

            price_allowances = _direct_children(price, CAC_NS, "AllowanceCharge")
            for allowance in price_allowances:
                charge_indicator = _find(allowance, "cbc:ChargeIndicator")
                is_allowance = charge_indicator is None or (charge_indicator.text or "").strip().lower() == "false"
                if not is_allowance:
                    continue

                allowance_amount_el = _find(allowance, "cbc:Amount")
                base_amount_el = _find(allowance, "cbc:BaseAmount")
                if allowance_amount_el is None or base_amount_el is None:
                    continue

                allowance_amount = _text_money(allowance_amount_el)
                _set_money(
                    allowance_amount_el,
                    allowance_amount,
                    report,
                    f"InvoiceLine[{line_id}].PriceAllowanceAmount",
                )
                expected_gross = _q(price_amount + allowance_amount)
                before_count = len(report["changes"])
                _set_money(
                    base_amount_el,
                    expected_gross,
                    report,
                    f"InvoiceLine[{line_id}].PriceBaseAmount",
                )
                if (
                    len(report["changes"]) > before_count
                    and "BR-KSA-EN16931-07" not in report["rules"]
                ):
                    report["rules"].append("BR-KSA-EN16931-07")
                # RUKN emits a single price allowance. If a future version emits more,
                # process each independently rather than combining unrelated bases.

    legal_total = _find(root, "cac:LegalMonetaryTotal")
    if legal_total is not None:
        line_extension_total = _find(legal_total, "cbc:LineExtensionAmount")
        if line_extension_total is not None:
            before_count = len(report["changes"])
            _set_money(line_extension_total, _q(line_extension_sum), report, "LegalMonetaryTotal.LineExtensionAmount")
            if len(report["changes"]) > before_count and "BR-CO-10" not in report["rules"]:
                report["rules"].append("BR-CO-10")

    # 2) Normalize document-level allowance total to what is actually rendered.
    doc_allowance_sum = Decimal("0.00")
    for allowance in _direct_children(root, CAC_NS, "AllowanceCharge"):
        charge_indicator = _find(allowance, "cbc:ChargeIndicator")
        is_allowance = charge_indicator is None or (charge_indicator.text or "").strip().lower() == "false"
        if is_allowance:
            doc_allowance_sum += _text_money(_find(allowance, "cbc:Amount"))

    if legal_total is not None:
        allowance_total = _find(legal_total, "cbc:AllowanceTotalAmount")
        if allowance_total is not None:
            before_count = len(report["changes"])
            _set_money(allowance_total, _q(doc_allowance_sum), report, "LegalMonetaryTotal.AllowanceTotalAmount")
            if len(report["changes"]) > before_count and "BR-CO-11" not in report["rules"]:
                report["rules"].append("BR-CO-11")

    # 3) The first top-level TaxTotal is the invoice-currency VAT total in RUKN's template.
    top_tax_totals = _direct_children(root, CAC_NS, "TaxTotal")
    invoice_tax_total = Decimal("0.00")
    if top_tax_totals:
        invoice_tax = top_tax_totals[0]
        subtotal_nodes = _direct_children(invoice_tax, CAC_NS, "TaxSubtotal")
        tax_amount_el = _find(invoice_tax, "cbc:TaxAmount")
        if subtotal_nodes:
            subtotal_sum = sum(
                (_text_money(_find(subtotal, "cbc:TaxAmount")) for subtotal in subtotal_nodes),
                Decimal("0.00"),
            )
            before_count = len(report["changes"])
            _set_money(tax_amount_el, _q(subtotal_sum), report, "TaxTotal.TaxAmount")
            if len(report["changes"]) > before_count and "BR-CO-14" not in report["rules"]:
                report["rules"].append("BR-CO-14")
        invoice_tax_total = _text_money(tax_amount_el)

    # 4) Legal monetary totals. Preserve PayableAmount and express any small delta as
    # PayableRoundingAmount instead of changing VAT/accounting values.
    if legal_total is not None:
        tax_exclusive_el = _find(legal_total, "cbc:TaxExclusiveAmount")
        tax_inclusive_el = _find(legal_total, "cbc:TaxInclusiveAmount")
        payable_el = _find(legal_total, "cbc:PayableAmount")
        prepaid_el = _find(legal_total, "cbc:PrepaidAmount")
        rounding_el = _find(legal_total, "cbc:PayableRoundingAmount")

        tax_exclusive = _text_money(tax_exclusive_el)
        expected_tax_inclusive = _q(tax_exclusive + invoice_tax_total)
        payable = _text_money(payable_el) if payable_el is not None else expected_tax_inclusive
        prepaid = _text_money(prepaid_el)
        required_rounding = _q(payable + prepaid - expected_tax_inclusive)
        max_rounding = abs(_q(max_payable_rounding))

        if abs(required_rounding) <= max_rounding:
            before_count = len(report["changes"])
            _set_money(tax_inclusive_el, expected_tax_inclusive, report, "LegalMonetaryTotal.TaxInclusiveAmount")
            if len(report["changes"]) > before_count and "BR-CO-15" not in report["rules"]:
                report["rules"].append("BR-CO-15")

            if required_rounding == Decimal("0.00"):
                if rounding_el is not None:
                    old = _text_money(rounding_el)
                    legal_total.remove(rounding_el)
                    report["changes"].append(
                        {
                            "field": "LegalMonetaryTotal.PayableRoundingAmount",
                            "old": _money_text(old),
                            "new": "removed",
                        }
                    )
                    if "BR-CO-16" not in report["rules"]:
                        report["rules"].append("BR-CO-16")
            else:
                if rounding_el is None:
                    rounding_el = ET.Element(f"{{{CBC_NS}}}PayableRoundingAmount")
                    currency_id = None
                    if payable_el is not None:
                        currency_id = payable_el.attrib.get("currencyID")
                    elif tax_inclusive_el is not None:
                        currency_id = tax_inclusive_el.attrib.get("currencyID")
                    if currency_id:
                        rounding_el.set("currencyID", currency_id)

                    children = list(legal_total)
                    insert_before = prepaid_el if prepaid_el is not None else payable_el
                    if insert_before is not None and insert_before in children:
                        legal_total.insert(children.index(insert_before), rounding_el)
                    else:
                        legal_total.append(rounding_el)
                    rounding_el.text = "0.00"

                before_count = len(report["changes"])
                _set_money(
                    rounding_el,
                    required_rounding,
                    report,
                    "LegalMonetaryTotal.PayableRoundingAmount",
                )
                if len(report["changes"]) > before_count and "BR-CO-16" not in report["rules"]:
                    report["rules"].append("BR-CO-16")
        else:
            report["warnings"].append(
                "Skipped LegalMonetaryTotal auto-fix because the required payable rounding "
                f"({required_rounding}) exceeds the safety limit ({max_rounding})."
            )

    report["changed"] = bool(report["changes"])

    if had_declaration:
        normalized = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    else:
        normalized = ET.tostring(root, encoding="unicode")

    return normalized, report


def normalize_xml_copy(xml_text: str, **kwargs) -> str:
    """Compatibility helper returning only normalized XML."""
    normalized, _ = normalize_xml(xml_text, **kwargs)
    return normalized
