from __future__ import annotations

from typing import Callable

_PATCH_APPLIED = False
_ORIGINAL_GENERATE_XML: Callable | None = None


def apply_patches(*args, **kwargs):
    """Install a runtime wrapper around RUKN's XML generator.

    This is called from both ``before_request`` and ``before_job`` so web submissions,
    live-sync background jobs, and the RUKN "Fix Rejection" flow all generate normalized
    XML without modifying the RUKN app itself.
    """

    global _PATCH_APPLIED, _ORIGINAL_GENERATE_XML

    try:
        import frappe
        import ksa_compliance.generate_xml as generate_xml_module
        from ksa_compliance.ksa_compliance.doctype.sales_invoice_additional_fields import (
            sales_invoice_additional_fields as siaf_module,
        )

        # If another import/reload restored RUKN's original alias, patch it again.
        current = getattr(generate_xml_module, "generate_xml_file", None)
        if getattr(current, "_zatca_fix_wrapper", False):
            wrapper = current
        else:
            if current is None:
                return
            _ORIGINAL_GENERATE_XML = current

            def wrapper(data: dict):
                from zatca_fix.xml_patch import normalize_xml

                raw_xml = _ORIGINAL_GENERATE_XML(data)
                normalized_xml, report = normalize_xml(raw_xml)

                if report.get("warnings"):
                    frappe.logger("zatca_fix").warning(
                        "ZATCA XML normalization warnings: %s", "; ".join(report["warnings"])
                    )
                if report.get("changed"):
                    frappe.logger("zatca_fix").info(
                        "Normalized ZATCA XML fields for rules: %s",
                        ", ".join(report.get("rules") or []),
                    )
                return normalized_xml

            wrapper._zatca_fix_wrapper = True
            wrapper._zatca_fix_original = current
            generate_xml_module.generate_xml_file = wrapper

        # RUKN imports generate_xml_file directly into this module, so patch that alias too.
        siaf_module.generate_xml_file = wrapper
        _PATCH_APPLIED = True
    except Exception:
        # Do not break Desk/login if RUKN is temporarily unavailable during migrations/builds.
        try:
            import frappe

            frappe.logger("zatca_fix").exception("Unable to install ZATCA XML runtime patch")
        except Exception:
            pass


def is_patch_applied() -> bool:
    return _PATCH_APPLIED
