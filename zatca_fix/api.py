import frappe
from frappe.utils import flt

@frappe.whitelist()
def fix_zatca_invoices(invoices):
    import json
    if isinstance(invoices, str):
        invoices = json.loads(invoices)
        
    for inv_name in invoices:
        doc = frappe.get_doc("Sales Invoice", inv_name)
        if doc.docstatus != 1:
            frappe.throw(f"الفاتورة {inv_name} يجب أن تكون معتمدة (مرحلة) أولاً.")
            
        is_tax_included = False
        if doc.get("taxes") and doc.taxes[0].included_in_print_rate:
            is_tax_included = True

        sum_line_ext = 0.0
        
        for item in doc.items:
            tax_percent = 0.0
            if doc.get("taxes"):
                try:
                    tax_detail = json.loads(doc.taxes[0].item_wise_tax_detail or "{}")
                    if item.item_code in tax_detail:
                        tax_percent = flt(tax_detail[item.item_code][0])
                except Exception:
                    pass
            
            amount = item.amount
            if is_tax_included:
                amount = flt(abs(amount) / (1 + (tax_percent / 100.0)), 2)
            
            sum_line_ext += flt(amount, 2)
            
        new_net_total = flt(sum_line_ext, 2)
        
        frappe.db.sql("""
            UPDATE `tabSales Invoice`
            SET base_net_total = %s, net_total = %s
            WHERE name = %s
        """, (new_net_total, new_net_total, doc.name))
        
        frappe.cache().hdel("Sales Invoice", inv_name)
        
    return "Success"
