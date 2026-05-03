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
	Analyze invoice for rounding issues using simplified detection method
	
	Detection Method:
	Difference = grand_total - (net_total + total_taxes_and_charges)
	If Difference != 0 and Difference < 0.10, it's a rounding error
	
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
		
		# Simple detection method
		net_total = float(invoice.net_total or 0)
		total_taxes = float(invoice.total_taxes_and_charges or 0)
		grand_total = float(invoice.grand_total or 0)
		
		calculated_total = net_total + total_taxes
		difference = round(grand_total - calculated_total, 2)
		
		# Rounding error if difference is not zero but less than 0.10
		has_issue = (difference != 0) and (abs(difference) < 0.10)
		
		# Detailed items analysis for fixing
		items_analysis = []
		items_calculated_total = 0
		
		for item in invoice.items:
			item_calculated_total = float(item.net_amount or 0) + float(item.tax_amount or 0)
			item_stored_total = float(item.amount or 0)
			item_difference = round(item_calculated_total - item_stored_total, 2)
			
			items_calculated_total += item_calculated_total
			
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
		
		problematic_items = [item for item in items_analysis if item["has_issue"]]
		
		return {
			"success": True,
			"invoice_name": invoice.name,
			"detection_method": "grand_total - (net_total + total_taxes_and_charges)",
			"net_total": round(net_total, 2),
			"total_taxes_and_charges": round(total_taxes, 2),
			"calculated_total": round(calculated_total, 2),
			"grand_total": round(grand_total, 2),
			"difference": difference,
			"has_issue": has_issue,
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
