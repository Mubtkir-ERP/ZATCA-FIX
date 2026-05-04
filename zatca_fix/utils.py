# -*- coding: utf-8 -*-
"""
ZATCA Fix - POS Rounding Issues Utility
========================================

This module provides automatic fixing for POS invoice rounding issues
that cause ZATCA BR-CO-15 validation errors.

The fix_pos_rounding_issues function is called automatically on Sales Invoice
validate event via doc_events hook.
"""

import frappe
import json
from frappe.utils import flt


def fix_pos_rounding_issues(doc, method=None):
    if not (doc.is_pos and doc.taxes and doc.taxes[0].included_in_print_rate):
        return
    
    menu_total = flt(
        sum(flt(item.qty) * flt(item.price_list_rate) for item in doc.items), 
        2
    )
    
    current_system_total = flt(doc.net_total + doc.total_taxes_and_charges, 2)
    
    diff = flt(menu_total - current_system_total, 2)
    
    if diff != 0 and abs(diff) <= 0.05:
        if not doc.items:
            return
        
        target_item = doc.items[0]
        
        target_item.tax_amount = flt(target_item.tax_amount + diff, 2)
        
        target_item.total_amount = flt(
            target_item.net_amount + target_item.tax_amount, 
            2
        )
        target_item.base_amount = target_item.total_amount
        
        new_tax_total = flt(
            sum(flt(row.tax_amount) for row in doc.items), 
            2
        )
        
        tax_row = doc.taxes[0]
        tax_row.tax_amount = new_tax_total
        tax_row.base_tax_amount = new_tax_total
        tax_row.tax_amount_after_discount_amount = new_tax_total
        
        tax_detail = {}
        for row in doc.items:
            tax_detail[row.item_code or row.item_name] = [
                flt(tax_row.rate), 
                flt(row.tax_amount)
            ]
        tax_row.item_wise_tax_detail = json.dumps(
            tax_detail, 
            separators=(',', ':')
        )
        
        doc.total_taxes_and_charges = new_tax_total
        doc.base_total_taxes_and_charges = new_tax_total
        doc.grand_total = menu_total
        doc.base_grand_total = menu_total
        
        # # ز- ضبط مبالغ الدفع لتجنب وجود متبقي (Outstanding)
        # if doc.payments:
        #     # نوزع الإجمالي الجديد على طرق الدفع (نعدل السطر الأول غالباً)
        #     doc.payments[0].amount = menu_total
        #     doc.payments[0].base_amount = menu_total
        #     doc.paid_amount = menu_total
        #     doc.base_paid_amount = menu_total
        #     doc.outstanding_amount = 0
        
        # ح- تصفير حقول التقريب التلقائية لمنع النظام من التدخل مرة أخرى
        doc.rounding_adjustment = 0
        doc.base_rounding_adjustment = 0
        
     