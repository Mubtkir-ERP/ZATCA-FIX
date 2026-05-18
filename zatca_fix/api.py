import frappe
from frappe.utils import flt, round_based_on_includes

@frappe.whitelist()
def fix_zatca_invoices(invoices):
    import json
    if isinstance(invoices, str):
        invoices = json.loads(invoices)
        
    for inv_name in invoices:
        doc = frappe.get_doc("Sales Invoice", inv_name)
        if doc.docstatus != 1:
            frappe.throw(f"الفاتورة {inv_name} يجب أن تكون معتمدة (مرحلة) أولاً.")
            
        target_total = flt(doc.base_net_total, 2)
        sum_amount = 0.0
        
        items = doc.get("items")
        
        for i, item in enumerate(items):
            if i < len(items) - 1:
                new_amount = flt(item.amount, 2)
                sum_amount += new_amount
            else:
                new_amount = flt(target_total - sum_amount, 2)
                
            new_rate = flt(new_amount / item.qty, 5) if item.qty else 0.0
            
            if item.discount_amount:
                total_disc = flt(item.discount_amount * item.qty, 2)
                new_disc_amount = flt(total_disc / item.qty, 5) if item.qty else 0.0
            else:
                new_disc_amount = 0.0
                
            frappe.db.sql("""
                UPDATE `tabSales Invoice Item`
                SET 
                    amount = %s,
                    base_amount = %s,
                    net_amount = %s,
                    base_net_amount = %s,
                    rate = %s,
                    base_rate = %s,
                    net_rate = %s,
                    discount_amount = %s
                WHERE name = %s
            """, (new_amount, new_amount, new_amount, new_amount, new_rate, new_rate, new_rate, new_disc_amount, item.name))
            
            # Recalculate item tax amount
            # Assuming tax is a simple percentage for ZATCA, we can find the tax detail for this item
            item_tax_rate = 15.0 # default
            if doc.get("taxes"):
                for t in doc.taxes:
                    try:
                        tax_detail = json.loads(t.item_wise_tax_detail)
                        if item.item_code in tax_detail:
                            item_tax_rate = flt(tax_detail[item.item_code][0])
                            break
                    except Exception:
                        pass
                        
            new_tax_amount = flt(new_amount * item_tax_rate / 100.0, 2)
            
            # Update item-wise tax detail in the database
            # This is complex because item_wise_tax_detail is a JSON string in Sales Taxes and Charges
            for t in doc.get("taxes"):
                try:
                    tax_detail = json.loads(t.item_wise_tax_detail or "{}")
                    if item.item_code in tax_detail:
                        tax_detail[item.item_code][1] = new_tax_amount
                        frappe.db.set_value("Sales Taxes and Charges", t.name, "item_wise_tax_detail", json.dumps(tax_detail), update_modified=False)
                except Exception:
                    pass
        
        # Finally, clear any cached zatca status or xml if needed (from additional fields)
        # Assuming Fatoora XML might be cached somewhere, but `bench clear-cache` works globally.
        # Just clear document cache
        frappe.cache().hdel("Sales Invoice", inv_name)
        
    return "Success"
