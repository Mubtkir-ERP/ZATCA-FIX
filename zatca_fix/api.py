# -*- coding: utf-8 -*-
# Copyright (c) 2024, Zatca Fix and contributors
# For license information, please see license.txt

"""
ZATCA Fix API
Fix BR-CO-15 rounding issues in Sales Invoices
"""

import frappe
from frappe import _


@frappe.whitelist()
def execute_sql(query):
	"""
	Execute SQL query to fix invoice rounding issues
	
	Args:
		query: SQL query string
		
	Returns:
		dict: Success status
	"""
	try:
		frappe.db.sql(query)
		frappe.db.commit()
		return {"success": True, "message": _("Query executed successfully")}
	except Exception as e:
		frappe.log_error(f"ZATCA Fix SQL Error: {str(e)}", "ZATCA Fix")
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def analyze_invoice(invoice_name):
	"""
	Analyze invoice for rounding issues
	
	Args:
		invoice_name: Name of the Sales Invoice
		
	Returns:
		dict: Analysis results
	"""
	try:
		invoice = frappe.get_doc("Sales Invoice", invoice_name)
		
		if invoice.docstatus != 1:
			return {
				"success": False,
				"message": _("Invoice is not submitted")
			}
		
		items_analysis = []
		calculated_total = 0
		
		for item in invoice.items:
			item_calculated_total = float(item.net_amount or 0) + float(item.tax_amount or 0)
			item_stored_total = float(item.amount or 0)
			item_difference = round(item_calculated_total - item_stored_total, 2)
			
			calculated_total += item_calculated_total
			
			items_analysis.append({
				"name": item.name,
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": item.qty,
				"rate": round(float(item.rate or 0), 2),
				"amount": round(float(item.amount or 0), 2),
				"net_amount": round(float(item.net_amount or 0), 2),
				"tax_rate": round(float(item.tax_rate or 0), 2),
				"tax_amount": round(float(item.tax_amount or 0), 2),
				"calculated_total": round(item_calculated_total, 2),
				"stored_total": item_stored_total,
				"difference": item_difference,
				"has_issue": abs(item_difference) > 0.001
			})
		
		calculated_total = round(calculated_total, 2)
		stored_grand_total = round(float(invoice.grand_total or 0), 2)
		total_difference = round(stored_grand_total - calculated_total, 2)
		
		problematic_items = [item for item in items_analysis if item["has_issue"]]
		
		return {
			"success": True,
			"invoice_name": invoice.name,
			"calculated_total": calculated_total,
			"stored_grand_total": stored_grand_total,
			"total_difference": total_difference,
			"has_issue": abs(total_difference) > 0.001,
			"items_count": len(invoice.items),
			"problematic_items_count": len(problematic_items),
			"items_analysis": items_analysis,
			"problematic_items": problematic_items
		}
		
	except Exception as e:
		frappe.log_error(f"ZATCA Fix Analysis Error: {str(e)}", "ZATCA Fix")
		return {
			"success": False,
			"message": str(e)
		}
