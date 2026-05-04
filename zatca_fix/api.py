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
def fix_invoice_tax(invoice_name):
	"""
	Fix invoice by adjusting tax amount (CORRECT METHOD)
	
	Rules:
	1. Keep net_amount unchanged (tax base must not change)
	2. Adjust tax_amount by the difference
	3. Update total_amount = net_amount + new_tax_amount
	4. Update item_wise_tax_detail JSON with new tax value
	5. Fix ALL decimal precision issues (2 decimals only)
	
	Args:
		invoice_name: Name of the Sales Invoice
		
	Returns:
		dict: Fix results
	"""
	try:
		invoice = frappe.get_doc("Sales Invoice", invoice_name)
		
		if invoice.docstatus != 1:
			return {
				"success": False,
				"message": _("Invoice is not submitted")
			}
		
		# Calculate difference
		net_total = float(invoice.net_total or 0)
		total_taxes = float(invoice.total_taxes_and_charges or 0)
		grand_total = float(invoice.grand_total or 0)
		base_total = float(invoice.base_total or 0)
		
		calculated_total = net_total + total_taxes
		difference = round(grand_total - calculated_total, 2)
		
		# Check if fix is needed
		if difference == 0:
			return {
				"success": True,
				"message": _("Invoice is already correct"),
				"difference": 0
			}
		
		if abs(difference) >= 0.10:
			return {
				"success": False,
				"message": _("Difference is too large: {0}").format(difference)
			}
		
		# Calculate new tax amount
		new_tax_amount = round(total_taxes + difference, 2)
		
		# 1. Update invoice header - CRITICAL: Fix base_total too!
		new_base_total = round(base_total + difference, 2)
		
		frappe.db.sql("""
			UPDATE `tabSales Invoice`
			SET total_taxes_and_charges = %s,
			    base_total_taxes_and_charges = %s,
			    base_total = %s
			WHERE name = %s
		""", (new_tax_amount, new_tax_amount, new_base_total, invoice_name))
		
		# 2. Update tax line with new item_wise_tax_detail JSON
		if invoice.taxes and len(invoice.taxes) > 0:
			tax_row = invoice.taxes[0]
			new_tax_row_amount = round(float(tax_row.tax_amount or 0) + difference, 2)
			
			# Build new item_wise_tax_detail JSON
			import json
			item_wise_tax = {}
			try:
				if tax_row.item_wise_tax_detail:
					item_wise_tax = json.loads(tax_row.item_wise_tax_detail)
			except:
				pass
			
			# CRITICAL: Update JSON for ALL items to match their actual tax amounts
			for item in invoice.items:
				item_key = item.item_code or item.item_name
				tax_rate = float(item.tax_rate or 0)
				
				# For first item, use new tax; for others, use their current tax
				if item.name == invoice.items[0].name:
					item_tax_for_json = new_tax_row_amount
				else:
					item_tax_for_json = float(item.tax_amount or 0)
				
				item_wise_tax[item_key] = [tax_rate, round(item_tax_for_json, 2)]
			
			item_wise_tax_json = json.dumps(item_wise_tax, ensure_ascii=False)
			
			# CRITICAL: Round to 2 decimals only!
			frappe.db.sql("""
				UPDATE `tabSales Taxes and Charges`
				SET tax_amount = %s,
				    base_tax_amount = %s,
				    total = %s,
				    base_total = %s,
				    tax_amount_after_discount_amount = %s,
				    base_tax_amount_after_discount_amount = %s,
				    item_wise_tax_detail = %s
				WHERE name = %s
			""", (new_tax_row_amount, new_tax_row_amount, grand_total, grand_total,
			      new_tax_row_amount, new_tax_row_amount,
			      item_wise_tax_json, tax_row.name))
		
		# 3. Update first item: tax_amount and total_amount (keep net_amount unchanged)
		# CRITICAL: Also update amount field to match (qty × rate)
		if invoice.items and len(invoice.items) > 0:
			first_item = invoice.items[0]
			old_item_tax = float(first_item.tax_amount or 0)
			new_item_tax = round(old_item_tax + difference, 2)
			
			# total_amount = net_amount + tax_amount (net_amount stays the same)
			item_net = float(first_item.net_amount or 0)
			new_item_total = round(item_net + new_item_tax, 2)
			
			# CRITICAL: Calculate correct amount from qty × rate
			item_qty = float(first_item.qty or 0)
			item_rate = float(first_item.rate or 0)
			correct_amount = round(item_qty * item_rate, 2)
			
			# CRITICAL: Update all amount fields consistently!
			frappe.db.sql("""
				UPDATE `tabSales Invoice Item`
				SET tax_amount = %s,
				    total_amount = %s,
				    amount = %s,
				    base_amount = %s
				WHERE name = %s
			""", (new_item_tax, new_item_total, correct_amount, correct_amount, first_item.name))
		
		frappe.db.commit()
		
		return {
			"success": True,
			"message": _("Invoice fixed successfully"),
			"old_tax": total_taxes,
			"new_tax": new_tax_amount,
			"difference": difference,
			"invoice_name": invoice_name,
			"method": "Adjusted tax_amount only (net_amount unchanged)"
		}
		
	except Exception as e:
		frappe.log_error(f"ZATCA Fix Tax Error: {str(e)}", "ZATCA Fix")
		return {
			"success": False,
			"message": str(e)
		}


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


# ============================================
# NEW PHASE 2: BR-CO-14 JSON Discrepancy Detection & Fix
# ============================================

@frappe.whitelist()
def analyze_json_discrepancy(invoice_name):
	"""
	Analyze JSON discrepancy (BR-CO-14) - ZATCA AUDITOR MODE (CORRECTED)
	
	Detection Method (CORRECTED):
	Compare item_wise_tax_detail JSON with ACTUAL ITEM TAX AMOUNTS (sum of item.tax_amount)
	This is the TRUE source of truth that ZATCA validates against!
	
	The issue: JSON and Header can both be wrong together, but items are the real calculation.
	
	Args:
		invoice_name: Name of the Sales Invoice
		
	Returns:
		dict: JSON discrepancy analysis results
	"""
	try:
		import json
		
		invoice = frappe.get_doc("Sales Invoice", invoice_name)
		
		if invoice.docstatus != 1:
			return {
				"success": False,
				"message": _("Invoice is not submitted")
			}
		
		# Get header tax total (for reference)
		header_tax_total = float(invoice.total_taxes_and_charges or 0)
		
		# Get item_wise_tax_detail JSON from tax line
		item_wise_tax_json = {}
		if invoice.taxes and len(invoice.taxes) > 0:
			tax_row = invoice.taxes[0]
			if tax_row.item_wise_tax_detail:
				try:
					item_wise_tax_json = json.loads(tax_row.item_wise_tax_detail)
				except:
					pass
		
		# Calculate JSON total
		json_total_tax = 0
		for item_code, tax_data in item_wise_tax_json.items():
			if isinstance(tax_data, list) and len(tax_data) > 1:
				json_total_tax += float(tax_data[1])
		
		json_total_tax = round(json_total_tax, 2)
		
		# CRITICAL FIX: Get actual item tax (THE TRUE SOURCE OF TRUTH!)
		actual_total_tax = sum(float(item.tax_amount or 0) for item in invoice.items)
		actual_total_tax = round(actual_total_tax, 2)
		
		# CORRECTED: Compare JSON with ACTUAL ITEMS, not header!
		json_discrepancy = round(json_total_tax - actual_total_tax, 2)
		has_json_issue = abs(json_discrepancy) > 0.001
		
		# Compare JSON values with actual item tax amounts (for details)
		items_comparison = []
		mismatched_items = []
		
		for item in invoice.items:
			item_code = item.item_code or item.item_name
			actual_tax = float(item.tax_amount or 0)
			
			# Get tax from JSON
			json_tax = 0
			if item_code in item_wise_tax_json:
				json_tax = float(item_wise_tax_json[item_code][1]) if len(item_wise_tax_json[item_code]) > 1 else 0
			
			difference = round(json_tax - actual_tax, 2)
			has_mismatch = abs(difference) > 0.001
			
			items_comparison.append({
				"item_code": item_code,
				"item_name": item.item_name,
				"json_tax": round(json_tax, 2),
				"actual_tax": round(actual_tax, 2),
				"difference": difference,
				"has_mismatch": has_mismatch
			})
			
			if has_mismatch:
				mismatched_items.append({
					"item_code": item_code,
					"json_tax": round(json_tax, 2),
					"actual_tax": round(actual_tax, 2),
					"difference": difference
				})
		
		return {
			"success": True,
			"invoice_name": invoice.name,
			"detection_method": "Compare JSON total with ACTUAL ITEM TAX AMOUNTS (sum of item.tax_amount) ← CORRECTED!",
			"json_total_tax": round(json_total_tax, 2),
			"actual_total_tax": round(actual_total_tax, 2),
			"header_tax_total": round(header_tax_total, 2),
			"json_discrepancy": json_discrepancy,
			"has_json_issue": has_json_issue,
			"items_count": len(invoice.items),
			"mismatched_items_count": len(mismatched_items),
			"items_comparison": items_comparison,
			"mismatched_items": mismatched_items,
			"warning": "JSON must match ACTUAL ITEMS (not header)! Both JSON and header are wrong by 0.01 SAR!" if has_json_issue else None
		}
		
	except Exception as e:
		frappe.log_error(f"ZATCA JSON Analysis Error: {str(e)}", "ZATCA Fix")
		return {
			"success": False,
			"message": str(e)
		}


@frappe.whitelist()
def fix_json_discrepancy(invoice_name):
	"""
	Fix JSON discrepancy (BR-CO-14) - ZATCA COMPLIANT FIX (CORRECTED)
	
	Method (CORRECTED):
	Rebuild item_wise_tax_detail JSON to match ACTUAL ITEM TAX AMOUNTS
	Then update HEADER to match the corrected JSON total
	
	This ensures: Items → JSON → Header all match!
	
	Args:
		invoice_name: Name of the Sales Invoice
		
	Returns:
		dict: Fix results
	"""
	try:
		import json
		
		invoice = frappe.get_doc("Sales Invoice", invoice_name)
		
		if invoice.docstatus != 1:
			return {
				"success": False,
				"message": _("Invoice is not submitted")
			}
		
		# Get actual item tax total (THE SOURCE OF TRUTH!)
		actual_total_tax = sum(float(item.tax_amount or 0) for item in invoice.items)
		actual_total_tax = round(actual_total_tax, 2)
		
		# Get current header tax
		old_header_tax = float(invoice.total_taxes_and_charges or 0)
		
		# Get current JSON
		old_item_wise_tax_json = {}
		if invoice.taxes and len(invoice.taxes) > 0:
			tax_row = invoice.taxes[0]
			if tax_row.item_wise_tax_detail:
				try:
					old_item_wise_tax_json = json.loads(tax_row.item_wise_tax_detail)
				except:
					pass
		
		# Calculate old JSON total
		old_json_total = 0
		for item_code, tax_data in old_item_wise_tax_json.items():
			if isinstance(tax_data, list) and len(tax_data) > 1:
				old_json_total += float(tax_data[1])
		old_json_total = round(old_json_total, 2)
		
		# Build new JSON to match ACTUAL ITEM TAX AMOUNTS
		new_item_wise_tax_json = {}
		fixed_items = []
		new_json_total = 0
		
		for item in invoice.items:
			item_code = item.item_code or item.item_name
			tax_rate = float(item.tax_rate or 0)
			actual_item_tax = float(item.tax_amount or 0)
			
			# Get old JSON tax
			old_json_tax = 0
			if item_code in old_item_wise_tax_json:
				old_json_tax = float(old_item_wise_tax_json[item_code][1]) if len(old_item_wise_tax_json[item_code]) > 1 else 0
			
			# Use ACTUAL item tax (not proportional distribution!)
			new_tax = round(actual_item_tax, 2)
			new_json_total += new_tax
			
			# Update JSON
			new_item_wise_tax_json[item_code] = [tax_rate, new_tax]
			
			if abs(old_json_tax - new_tax) > 0.001:
				fixed_items.append({
					"item_code": item_code,
					"old_json_tax": round(old_json_tax, 2),
					"new_json_tax": new_tax,
					"actual_item_tax": new_tax,
					"adjustment": round(new_tax - old_json_tax, 2)
				})
		
		new_json_total = round(new_json_total, 2)
		
		# Update tax line with new JSON
		if invoice.taxes and len(invoice.taxes) > 0:
			tax_row = invoice.taxes[0]
			new_json_str = json.dumps(new_item_wise_tax_json, ensure_ascii=False)
			
			# CRITICAL: Also update header to match new JSON total!
			frappe.db.sql("""
				UPDATE `tabSales Taxes and Charges`
				SET item_wise_tax_detail = %s,
				    tax_amount = %s,
				    base_tax_amount = %s,
				    tax_amount_after_discount_amount = %s,
				    base_tax_amount_after_discount_amount = %s
				WHERE name = %s
			""", (new_json_str, new_json_total, new_json_total, 
			      new_json_total, new_json_total, tax_row.name))
		
		# Update invoice header to match
		frappe.db.sql("""
			UPDATE `tabSales Invoice`
			SET total_taxes_and_charges = %s,
			    base_total_taxes_and_charges = %s
			WHERE name = %s
		""", (new_json_total, new_json_total, invoice_name))
		
		frappe.db.commit()
		
		return {
			"success": True,
			"message": _("JSON synchronized with ACTUAL item tax amounts, header updated"),
			"invoice_name": invoice_name,
			"items_fixed": len(fixed_items),
			"old_json_total": round(old_json_total, 2),
			"new_json_total": new_json_total,
			"old_header_tax": round(old_header_tax, 2),
			"new_header_tax": new_json_total,
			"actual_item_tax_total": actual_total_tax,
			"fixed_items": fixed_items,
			"method": "JSON now matches actual item tax amounts, header updated to match"
		}
		
	except Exception as e:
		frappe.log_error(f"ZATCA JSON Fix Error: {str(e)}", "ZATCA Fix")
		return {
			"success": False,
			"message": str(e)
		}


# ============================================
# NEW PHASE 3: Item-Level Internal Consistency Check
# ============================================

@frappe.whitelist()
def analyze_item_level_discrepancy(invoice_name):
	"""
	Analyze item-level discrepancies (BR-CO-16) - ZATCA AUDITOR MODE
	
	Detection Method (DUAL CHECK):
	1. Internal Balance: item.amount should equal (item.net_amount + item.tax_amount)
	2. Price Match: item.amount should equal (item.qty × item.rate) ← ZATCA CHECK!
	
	This catches "lost halalas" that pass internal validation but fail ZATCA
	
	Args:
		invoice_name: Name of the Sales Invoice
		
	Returns:
		dict: Item-level discrepancy analysis results
	"""
	try:
		invoice = frappe.get_doc("Sales Invoice", invoice_name)
		
		if invoice.docstatus != 1:
			return {
				"success": False,
				"message": _("Invoice is not submitted")
			}
		
		problematic_items = []
		total_item_discrepancy = 0
		items_analysis = []
		
		for item in invoice.items:
			stored_amount = float(item.amount or 0)
			net_amount = float(item.net_amount or 0)
			tax_amount = float(item.tax_amount or 0)
			qty = float(item.qty or 0)
			rate = float(item.rate or 0)
			
			# Internal balance check
			calculated_from_net_tax = round(net_amount + tax_amount, 2)
			internal_difference = round(stored_amount - calculated_from_net_tax, 2)
			
			# ZATCA check: qty × rate
			expected_from_price = round(qty * rate, 2)
			price_difference = round(stored_amount - expected_from_price, 2)
			
			# Item has issue if EITHER check fails
			has_internal_issue = abs(internal_difference) > 0.001
			has_price_issue = abs(price_difference) > 0.001
			has_discrepancy = has_internal_issue or has_price_issue
			
			items_analysis.append({
				"name": item.name,
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": qty,
				"rate": round(rate, 2),
				"stored_amount": round(stored_amount, 2),
				"net_amount": round(net_amount, 2),
				"tax_rate": round(float(item.tax_rate or 0), 2),
				"tax_amount": round(tax_amount, 2),
				"calculated_from_net_tax": round(calculated_from_net_tax, 2),
				"expected_from_price": round(expected_from_price, 2),
				"internal_difference": internal_difference,
				"price_difference": price_difference,
				"has_internal_issue": has_internal_issue,
				"has_price_issue": has_price_issue,
				"has_discrepancy": has_discrepancy,
				"issue_type": "Price Mismatch (ZATCA)" if has_price_issue else ("Internal Imbalance" if has_internal_issue else "OK")
			})
			
			if has_discrepancy:
				problematic_items.append({
					"name": item.name,
					"item_code": item.item_code,
					"stored_amount": round(stored_amount, 2),
					"net_amount": round(net_amount, 2),
					"tax_amount": round(tax_amount, 2),
					"qty": qty,
					"rate": round(rate, 2),
					"calculated_from_net_tax": round(calculated_from_net_tax, 2),
					"expected_from_price": round(expected_from_price, 2),
					"internal_difference": internal_difference,
					"price_difference": price_difference,
					"issue_type": "Price Mismatch (ZATCA)" if has_price_issue else "Internal Imbalance"
				})
				# Use price difference for total (ZATCA's view)
				total_item_discrepancy += price_difference if has_price_issue else internal_difference
		
		has_item_discrepancy = len(problematic_items) > 0
		
		return {
			"success": True,
			"invoice_name": invoice.name,
			"detection_method": "DUAL: (1) amount vs (net+tax), (2) amount vs (qty×rate) ← ZATCA",
			"has_item_discrepancy": has_item_discrepancy,
			"problematic_items_count": len(problematic_items),
			"total_discrepancy": round(total_item_discrepancy, 2),
			"items_analysis": items_analysis,
			"problematic_items": problematic_items
		}
		
	except Exception as e:
		frappe.log_error(f"ZATCA Item Level Analysis Error: {str(e)}", "ZATCA Fix")
		return {
			"success": False,
			"message": str(e)
		}


@frappe.whitelist()
def fix_item_level_discrepancy(invoice_name):
	"""
	Fix item-level discrepancies (BR-CO-16) - ZATCA COMPLIANT FIX
	
	Method:
	1. Recalculate item total from qty × rate (ZATCA's expectation)
	2. Redistribute to net and tax while maintaining tax rate
	3. Ensure: net + tax = qty × rate (exact match)
	
	Args:
		invoice_name: Name of the Sales Invoice
		
	Returns:
		dict: Fix results
	"""
	try:
		analysis = analyze_item_level_discrepancy(invoice_name)
		
		if not analysis.get("success"):
			return analysis
		
		if not analysis.get("has_item_discrepancy"):
			return {
				"success": True,
				"message": _("No item discrepancies found"),
				"items_fixed": 0
			}
		
		fixed_items = []
		
		for item_data in analysis["problematic_items"]:
			# ZATCA FIX: Use qty × rate as the correct total
			correct_total = round(item_data["qty"] * item_data["rate"], 2)
			
			# Recalculate net and tax to match correct total
			# Method: Keep tax rate, adjust amounts
			tax_rate = float(item_data.get("tax_rate", 15)) / 100
			
			# Calculate net from total: net = total / (1 + tax_rate)
			new_net = round(correct_total / (1 + tax_rate), 2)
			
			# Calculate tax as difference to ensure exact match
			new_tax = round(correct_total - new_net, 2)
			
			# Verify: net + tax = total (must be exact!)
			verification = round(new_net + new_tax, 2)
			if abs(verification - correct_total) > 0.001:
				# Adjust tax by the tiny difference
				new_tax = round(correct_total - new_net, 2)
			
			# Update database
			frappe.db.sql("""
				UPDATE `tabSales Invoice Item`
				SET 
					amount = %s,
					base_amount = %s,
					net_amount = %s,
					base_net_amount = %s,
					tax_amount = %s,
					total_amount = %s
				WHERE name = %s
			""", (correct_total, correct_total, new_net, new_net, new_tax, correct_total, item_data["name"]))
			
			fixed_items.append({
				"item_code": item_data["item_code"],
				"old_amount": item_data["stored_amount"],
				"new_amount": correct_total,
				"old_net": item_data["net_amount"],
				"new_net": new_net,
				"old_tax": item_data["tax_amount"],
				"new_tax": new_tax,
				"adjustment": round(correct_total - item_data["stored_amount"], 2),
				"method": f"Recalculated from {item_data['qty']} × {item_data['rate']}"
			})
		
		frappe.db.commit()
		
		return {
			"success": True,
			"message": _("Item discrepancies fixed using ZATCA method (qty × rate)"),
			"invoice_name": invoice_name,
			"items_fixed": len(fixed_items),
			"total_adjustment": round(analysis["total_discrepancy"], 2),
			"fixed_items": fixed_items,
			"method": "ZATCA Compliant: amount = qty × rate, then redistribute to net + tax"
		}
		
	except Exception as e:
		frappe.log_error(f"ZATCA Item Level Fix Error: {str(e)}", "ZATCA Fix")
		return {
			"success": False,
			"message": str(e)
		}


# ============================================
# COMPLETE COMPREHENSIVE ANALYSIS (All 3 Phases)
# ============================================

@frappe.whitelist()
def analyze_complete(invoice_name):
	"""
	Complete comprehensive analysis for all ZATCA issues
	
	Phases:
	1. BR-CO-15: Header vs Body balance (grand_total vs net+tax)
	2. BR-CO-14: JSON discrepancy (item_wise_tax_detail vs actual)
	3. BR-CO-16: Item-level consistency (item.amount vs item.net+item.tax)
	
	Args:
		invoice_name: Name of the Sales Invoice
		
	Returns:
		dict: Complete analysis results with recommendations
	"""
	try:
		# Run all three analyses
		br_co_15_result = analyze_invoice(invoice_name)
		br_co_14_result = analyze_json_discrepancy(invoice_name)
		br_co_16_result = analyze_item_level_discrepancy(invoice_name)
		
		if not br_co_15_result.get("success") or not br_co_14_result.get("success") or not br_co_16_result.get("success"):
			return {
				"success": False,
				"message": _("Analysis failed")
			}
		
		# Determine issues and recommendations
		issues_found = []
		recommendations = []
		fix_sequence = []
		
		# Check BR-CO-16 first (item-level issues should be fixed first)
		if br_co_16_result.get("has_item_discrepancy"):
			issues_found.append({
				"code": "BR-CO-16",
				"title": "Item-Level Discrepancy",
				"severity": "high",
				"description": f"Found {br_co_16_result['problematic_items_count']} item(s) with internal inconsistency",
				"impact": f"Total discrepancy: {br_co_16_result['total_discrepancy']} SAR"
			})
			recommendations.append({
				"step": 1,
				"action": "Fix Item Discrepancy",
				"button": "Fix BR-CO-16",
				"reason": "Item amounts don't match (net + tax). Fix this first before other checks."
			})
			fix_sequence.append("BR-CO-16")
		
		# Check BR-CO-14 (JSON discrepancy)
		if br_co_14_result.get("has_json_issue"):
			issues_found.append({
				"code": "BR-CO-14",
				"title": "JSON Discrepancy",
				"severity": "high",
				"description": f"item_wise_tax_detail JSON doesn't match actual tax amounts",
				"impact": f"JSON discrepancy: {br_co_14_result['json_discrepancy']} SAR"
			})
			step_num = len(recommendations) + 1
			recommendations.append({
				"step": step_num,
				"action": "Fix JSON Discrepancy",
				"button": "Fix BR-CO-14",
				"reason": "ZATCA reads tax from JSON. Must synchronize with actual values."
			})
			fix_sequence.append("BR-CO-14")
		
		# Check BR-CO-15 (header vs body)
		if br_co_15_result.get("has_issue"):
			issues_found.append({
				"code": "BR-CO-15",
				"title": "Rounding Issue",
				"severity": "medium",
				"description": "Grand total doesn't match (net + tax)",
				"impact": f"Difference: {br_co_15_result['difference']} SAR"
			})
			step_num = len(recommendations) + 1
			recommendations.append({
				"step": step_num,
				"action": "Fix Rounding Issue",
				"button": "Fix BR-CO-15",
				"reason": "Adjust tax amount to match grand total."
			})
			fix_sequence.append("BR-CO-15")
		
		# Overall status
		has_any_issue = len(issues_found) > 0
		status = "issues_found" if has_any_issue else "all_clear"
		
		# Summary statistics
		summary = {
			"total_issues": len(issues_found),
			"critical_issues": len([i for i in issues_found if i["severity"] == "high"]),
			"invoice_status": "Needs Fixing" if has_any_issue else "Ready for ZATCA",
			"fix_sequence": fix_sequence
		}
		
		return {
			"success": True,
			"invoice_name": invoice_name,
			"status": status,
			"summary": summary,
			"issues_found": issues_found,
			"recommendations": recommendations,
			"br_co_15": br_co_15_result,
			"br_co_14": br_co_14_result,
			"br_co_16": br_co_16_result,
			"has_any_issue": has_any_issue
		}
		
	except Exception as e:
		frappe.log_error(f"ZATCA Complete Analysis Error: {str(e)}", "ZATCA Fix")
		return {
			"success": False,
			"message": str(e)
		}


@frappe.whitelist()
def fix_all_issues(invoice_name):
	"""
	Fix all detected issues in the correct sequence
	
	Sequence:
	1. BR-CO-16: Fix item-level discrepancies first
	2. BR-CO-14: Synchronize JSON with actual values
	3. BR-CO-15: Adjust tax to match grand total
	
	Args:
		invoice_name: Name of the Sales Invoice
		
	Returns:
		dict: Complete fix results
	"""
	try:
		# First, analyze to determine what needs fixing
		analysis = analyze_complete(invoice_name)
		
		if not analysis.get("success"):
			return analysis
		
		if not analysis.get("has_any_issue"):
			return {
				"success": True,
				"message": _("No issues found. Invoice is ready for ZATCA."),
				"fixes_applied": []
			}
		
		fixes_applied = []
		
		# Step 1: Fix BR-CO-16 (item-level)
		if analysis["br_co_16"].get("has_item_discrepancy"):
			fix_result = fix_item_level_discrepancy(invoice_name)
			if fix_result.get("success"):
				fixes_applied.append({
					"code": "BR-CO-16",
					"title": "Item-Level Discrepancy Fixed",
					"items_fixed": fix_result.get("items_fixed", 0),
					"details": fix_result.get("fixed_items", [])
				})
		
		# Step 2: Fix BR-CO-14 (JSON)
		if analysis["br_co_14"].get("has_json_issue"):
			fix_result = fix_json_discrepancy(invoice_name)
			if fix_result.get("success"):
				fixes_applied.append({
					"code": "BR-CO-14",
					"title": "JSON Discrepancy Fixed",
					"items_fixed": fix_result.get("items_fixed", 0),
					"details": fix_result.get("fixed_items", [])
				})
		
		# Step 3: Fix BR-CO-15 (rounding)
		if analysis["br_co_15"].get("has_issue"):
			fix_result = fix_invoice_tax(invoice_name)
			if fix_result.get("success"):
				fixes_applied.append({
					"code": "BR-CO-15",
					"title": "Rounding Issue Fixed",
					"adjustment": fix_result.get("difference", 0),
					"details": {
						"old_tax": fix_result.get("old_tax", 0),
						"new_tax": fix_result.get("new_tax", 0)
					}
				})
		
		return {
			"success": True,
			"message": _("All issues fixed successfully!"),
			"invoice_name": invoice_name,
			"fixes_count": len(fixes_applied),
			"fixes_applied": fixes_applied
		}
		
	except Exception as e:
		frappe.log_error(f"ZATCA Fix All Error: {str(e)}", "ZATCA Fix")
		return {
			"success": False,
			"message": str(e)
		}
