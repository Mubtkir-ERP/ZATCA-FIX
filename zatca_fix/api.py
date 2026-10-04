from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP

import frappe
from frappe.utils import flt

from zatca_fix.runtime import apply_patches, is_patch_applied

MONEY = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _as_float(value: Decimal) -> float:
    return float(value)


def _get_invoice(invoice_name: str):
    doc = frappe.get_doc("Sales Invoice", invoice_name)
    if doc.docstatus != 1:
        frappe.throw(f"الفاتورة {invoice_name} يجب أن تكون معتمدة أولاً.")
    return doc


def _tax_rate_for_item(doc, item) -> float:
    if item.get("tax_rate") is not None:
        return abs(flt(item.get("tax_rate")))

    for tax_row in doc.get("taxes") or []:
        try:
            detail = json.loads(tax_row.item_wise_tax_detail or "{}")
            if item.item_code in detail:
                return abs(flt(detail[item.item_code][0]))
        except Exception:
            continue
    return 0.0


def _xml_line_net(doc, item, tax_rate: float) -> Decimal:
    amount = abs(flt(item.amount))
    is_tax_included = bool(doc.get("taxes") and doc.taxes[0].included_in_print_rate)
    if is_tax_included and tax_rate:
        amount = amount / (1 + (tax_rate / 100.0))
    return _money(amount)


def _build_analysis(doc) -> dict:
    items = []
    xml_line_sum = Decimal("0.00")
    item_issue_count = 0
    price_issue_count = 0

    for item in doc.items:
        tax_rate = _tax_rate_for_item(doc, item)
        line_net = _xml_line_net(doc, item, tax_rate)
        line_tax = _money(abs(flt(item.get("tax_amount") or 0)))
        expected_line_total = _money(line_net + line_tax)
        stored_line_total = _money(abs(flt(item.get("total_amount") or 0)))

        discount_total = _money(abs(flt(item.get("discount_amount") or 0)) * abs(flt(item.qty or 0)))
        expected_gross_price = _money(line_net + discount_total)

        line_issue = stored_line_total != expected_line_total
        if line_issue:
            item_issue_count += 1

        # RUKN derives BaseAmount from amount + discount. This flag shows when the rendered
        # two-decimal relationship needs XML normalization.
        raw_gross = Decimal(str(abs(flt(item.amount)))) + Decimal(
            str(abs(flt(item.get("discount_amount") or 0)) * abs(flt(item.qty or 0)))
        )
        rounded_raw_gross = _money(raw_gross)
        price_issue = rounded_raw_gross != expected_gross_price
        if price_issue:
            price_issue_count += 1

        xml_line_sum += line_net
        items.append(
            {
                "idx": item.idx,
                "item_code": item.item_code,
                "qty": abs(flt(item.qty)),
                "tax_rate": tax_rate,
                "xml_line_net": _as_float(line_net),
                "xml_line_tax": _as_float(line_tax),
                "expected_line_with_vat": _as_float(expected_line_total),
                "stored_total_amount": _as_float(stored_line_total),
                "line_rounding_difference": _as_float(_money(stored_line_total - expected_line_total)),
                "discount_total": _as_float(discount_total),
                "expected_gross_price": _as_float(expected_gross_price),
                "line_issue": line_issue,
                "price_issue": price_issue,
            }
        )

    net_total = _money(abs(flt(doc.net_total)))
    tax_total = _money(abs(flt(doc.total_taxes_and_charges)))
    grand_total = _money(abs(flt(doc.grand_total)))
    expected_tax_inclusive = _money(net_total + tax_total)
    inclusive_difference = _money(grand_total - expected_tax_inclusive)

    payable = _money(abs(flt(doc.rounded_total if not doc.is_rounded_total_disabled() else doc.grand_total)))
    prepaid = _money(abs(flt(doc.get("total_advance") or 0)))
    expected_rounding = _money(payable + prepaid - expected_tax_inclusive)

    return {
        "success": True,
        "invoice_name": doc.name,
        "patch_mode": "XML only - no accounting/database value changes",
        "net_total": _as_float(net_total),
        "tax_total": _as_float(tax_total),
        "grand_total": _as_float(grand_total),
        "expected_tax_inclusive": _as_float(expected_tax_inclusive),
        "tax_inclusive_difference": _as_float(inclusive_difference),
        "expected_payable_rounding": _as_float(expected_rounding),
        "xml_line_extension_sum": _as_float(_money(xml_line_sum)),
        "items": items,
        "item_rounding_issues": item_issue_count,
        "price_allowance_issues": price_issue_count,
        "has_issue": bool(inclusive_difference or item_issue_count or price_issue_count),
        "rules_covered": [
            "BR-KSA-51",
            "BR-KSA-EN16931-07",
            "BR-CO-10",
            "BR-CO-11",
            "BR-CO-14",
            "BR-CO-15",
            "BR-CO-16",
        ],
    }


@frappe.whitelist()
def get_patch_status():
    apply_patches()
    return {
        "success": True,
        "active": is_patch_applied(),
        "mode": "XML-only",
        "message": "ZATCA Fix normalizes RUKN XML before signing without changing submitted invoice accounting values.",
        "rules_covered": [
            "BR-KSA-51",
            "BR-KSA-EN16931-07",
            "BR-CO-10",
            "BR-CO-11",
            "BR-CO-14",
            "BR-CO-15",
            "BR-CO-16",
        ],
    }


@frappe.whitelist()
def analyze_invoice(invoice_name):
    apply_patches()
    return _build_analysis(_get_invoice(invoice_name))


@frappe.whitelist()
def analyze_complete(invoice_name):
    return analyze_invoice(invoice_name)


@frappe.whitelist()
def analyze_item_level_discrepancy(invoice_name):
    result = analyze_invoice(invoice_name)
    result["problematic_items"] = [x for x in result["items"] if x["line_issue"]]
    result["problematic_items_count"] = len(result["problematic_items"])
    result["has_item_discrepancy"] = bool(result["problematic_items"])
    return result


@frappe.whitelist()
def analyze_json_discrepancy(invoice_name):
    result = analyze_invoice(invoice_name)
    result.update(
        {
            "has_json_discrepancy": False,
            "message": "This version does not rewrite item_wise_tax_detail. ZATCA correction is applied to generated XML only.",
        }
    )
    return result


@frappe.whitelist()
def fix_invoice_tax(invoice_name):
    """Legacy API kept for old cached JavaScript.

    Previous versions changed tax values in submitted invoices. That behavior is deliberately
    removed. The runtime XML patch is now the fix.
    """
    doc = _get_invoice(invoice_name)
    apply_patches()
    current_tax = flt(doc.total_taxes_and_charges)
    return {
        "success": True,
        "invoice_name": invoice_name,
        "old_tax": current_tax,
        "new_tax": current_tax,
        "difference": 0,
        "mode": "XML-only",
        "message": "No tax/accounting values were changed. The XML fix is active for the next ZATCA generation.",
    }


@frappe.whitelist()
def fix_item_level_discrepancy(invoice_name):
    return fix_invoice_tax(invoice_name)


@frappe.whitelist()
def fix_json_discrepancy(invoice_name):
    return fix_invoice_tax(invoice_name)


@frappe.whitelist()
def fix_all_issues(invoice_name):
    result = analyze_invoice(invoice_name)
    apply_patches()
    return {
        "success": True,
        "invoice_name": invoice_name,
        "fixes_count": len(result["rules_covered"]),
        "fixes_applied": [
            {"code": code, "title": "Handled at XML generation time"} for code in result["rules_covered"]
        ],
        "mode": "XML-only",
        "message": "The runtime XML correction is active. No submitted invoice values were changed.",
    }


@frappe.whitelist()
def retry_rejected_invoice(invoice_name):
    """Use RUKN's official Fix Rejection flow after enabling the XML patch."""
    _get_invoice(invoice_name)
    apply_patches()

    latest = frappe.get_all(
        "Sales Invoice Additional Fields",
        filters={
            "sales_invoice": invoice_name,
            "invoice_doctype": "Sales Invoice",
            "is_latest": 1,
        },
        fields=["name", "integration_status", "docstatus"],
        order_by="creation desc",
        limit_page_length=1,
    )
    if not latest:
        frappe.throw("لم يتم العثور على Sales Invoice Additional Fields لهذه الفاتورة.")

    current = latest[0]
    if current.integration_status != "Rejected":
        frappe.throw(
            f"آخر سجل ZATCA حالته {current.integration_status or 'غير محددة'} وليس Rejected. لن تتم إعادة الإرسال تلقائياً."
        )

    from ksa_compliance.ksa_compliance.doctype.sales_invoice_additional_fields.sales_invoice_additional_fields import (
        fix_rejection,
    )

    old_name = current.name
    fix_rejection(old_name)

    new_latest = frappe.get_all(
        "Sales Invoice Additional Fields",
        filters={
            "sales_invoice": invoice_name,
            "invoice_doctype": "Sales Invoice",
            "is_latest": 1,
        },
        fields=["name", "integration_status", "docstatus"],
        order_by="creation desc",
        limit_page_length=1,
    )

    return {
        "success": True,
        "invoice_name": invoice_name,
        "old_additional_fields": old_name,
        "new_additional_fields": new_latest[0].name if new_latest else None,
        "status": new_latest[0].integration_status if new_latest else None,
        "message": "تم تشغيل Fix Rejection الرسمي من تطبيق RUKN. سيتم إنشاء XML جديد مع تصحيح ZATCA Fix.",
    }


@frappe.whitelist()
def fix_zatca_invoices(invoices):
    """Backward-compatible bulk endpoint. It no longer edits invoice totals."""
    if isinstance(invoices, str):
        invoices = json.loads(invoices)

    results = []
    for invoice_name in invoices or []:
        try:
            results.append(analyze_invoice(invoice_name))
        except Exception as exc:
            results.append({"success": False, "invoice_name": invoice_name, "message": str(exc)})

    apply_patches()
    return {
        "success": True,
        "mode": "XML-only",
        "results": results,
        "message": "لم يتم تعديل أي قيمة محاسبية. التصحيح يطبق عند توليد XML القادم.",
    }
