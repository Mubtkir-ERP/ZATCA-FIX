// ============================================
// ZATCA Fix - Sales Invoice Client Script
// Fix BR-CO-15 rounding issues by adjusting TAX
// ============================================

frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Add buttons only for submitted invoices
        if (frm.doc.docstatus === 1) {
            // ========== MAIN ACTIONS ==========
            
            // Complete Analysis (Recommended - Start Here)
            frm.add_custom_button(__('🔍 Complete Analysis'), function() {
                analyze_complete_invoice(frm);
            }, __('ZATCA'));
            
            // Fix All Issues (One-Click Fix)
            frm.add_custom_button(__('🔧 Fix All Issues'), function() {
                fix_all_issues(frm);
            }, __('ZATCA'));
            
            // ========== INDIVIDUAL FIXES ==========
            
            // Fix button for BR-CO-16 (Item-Level)
            frm.add_custom_button(__('Fix BR-CO-16 (Items)'), function() {
                fix_item_discrepancy(frm);
            }, __('ZATCA'));
            
            // Fix button for BR-CO-14 (JSON Discrepancy)
            frm.add_custom_button(__('Fix BR-CO-14 (JSON)'), function() {
                fix_json_discrepancy(frm);
            }, __('ZATCA'));
            
            // Fix button for BR-CO-15 (Rounding)
            frm.add_custom_button(__('Fix BR-CO-15 (Rounding)'), function() {
                fix_zatca_rounding_issue(frm);
            }, __('ZATCA'));
            
            // ========== INDIVIDUAL ANALYSES ==========
            
            // Analyze button for BR-CO-16
            frm.add_custom_button(__('Analyze BR-CO-16'), function() {
                analyze_item_discrepancy(frm);
            }, __('ZATCA'));
            
            // Analyze button for BR-CO-14
            frm.add_custom_button(__('Analyze BR-CO-14'), function() {
                analyze_json_discrepancy(frm);
            }, __('ZATCA'));
            
            // Analyze button for BR-CO-15
            frm.add_custom_button(__('Analyze BR-CO-15'), function() {
                analyze_invoice_only(frm);
            }, __('ZATCA'));
        }
    }
});

/**
 * Analyze invoice only without fixing
 */
function analyze_invoice_only(frm) {
    frappe.show_alert({
        message: __('Analyzing invoice...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'zatca_fix.api.analyze_invoice',
        args: {
            invoice_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                show_analysis_dialog(r.message, frm);
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.message || __('Analysis failed'),
                    indicator: 'red'
                });
            }
        }
    });
}

/**
 * Fix rounding issue by adjusting tax (correct method)
 */
function fix_zatca_rounding_issue(frm) {
    frappe.confirm(
        __('Do you want to fix the rounding issue in this invoice?<br><br>' +
           '<b>Method:</b> Adjust tax amount to match grand total<br>' +
           '<b>Note:</b> This will update tax fields directly without canceling submission.<br>' +
           'This is the correct method for ZATCA compliance.'),
        function() {
            fix_invoice_tax(frm);
        }
    );
}

/**
 * Fix invoice by adjusting tax amount
 */
function fix_invoice_tax(frm) {
    frappe.show_alert({
        message: __('Fixing invoice...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'zatca_fix.api.fix_invoice_tax',
        args: {
            invoice_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: __('Invoice fixed successfully!'),
                    indicator: 'green'
                });
                
                show_tax_fix_result(r.message);
                
                setTimeout(function() {
                    frm.reload_doc();
                }, 1500);
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.message || __('Fix failed'),
                    indicator: 'red'
                });
            }
        }
    });
}

/**
 * Show tax fix result
 */
function show_tax_fix_result(result) {
    let html = `
        <div style="padding: 15px;">
            <div class="alert alert-success">
                <strong>Fixed Successfully!</strong>
            </div>
            
            <table class="table table-bordered">
                <tr>
                    <td><b>Invoice:</b></td>
                    <td>${result.invoice_name}</td>
                </tr>
                <tr>
                    <td><b>Old Tax Amount:</b></td>
                    <td>${format_currency(result.old_tax)}</td>
                </tr>
                <tr>
                    <td><b>New Tax Amount:</b></td>
                    <td>${format_currency(result.new_tax)}</td>
                </tr>
                <tr>
                    <td><b>Adjustment:</b></td>
                    <td style="color: green; font-weight: bold;">
                        ${format_currency(result.difference)}
                    </td>
                </tr>
            </table>
            
            <div class="alert alert-info" style="margin-top: 15px;">
                <strong>What was fixed:</strong>
                <ul style="margin-bottom: 0;">
                    <li>Tax amount adjusted by ${format_currency(result.difference)}</li>
                    <li>Invoice header updated</li>
                    <li>Tax line updated</li>
                    <li>Item tax amounts updated</li>
                </ul>
            </div>
            
            <p style="margin-top: 15px; color: #666;">
                <i class="fa fa-info-circle"></i>
                Tax adjusted to match grand total. Net amount unchanged.
            </p>
        </div>
    `;
    
    frappe.msgprint({
        title: __('Fix Result'),
        message: html,
        indicator: 'green',
        wide: true
    });
}

/**
 * Show analysis dialog
 */
function show_analysis_dialog(analysis, frm) {
    let solution_html = '';
    
    if (analysis.has_issue) {
        let new_tax = analysis.total_taxes_and_charges + analysis.difference;
        
        // Get first item info for SQL
        let first_item = analysis.items_analysis && analysis.items_analysis.length > 0 ? analysis.items_analysis[0] : null;
        let item_net = first_item ? first_item.net_amount : 0;
        let item_old_tax = first_item ? first_item.tax_amount : 0;
        let item_new_tax = item_old_tax + analysis.difference;
        let item_new_total = item_net + item_new_tax;
        let item_name = first_item ? first_item.name : '';
        let item_code = first_item ? first_item.item_code : '';
        let tax_rate = first_item ? first_item.tax_rate : 15;
        
        solution_html = `
            <div class="alert alert-info" style="margin-top: 20px;">
                <h5><i class="fa fa-wrench"></i> Solution (Correct Method):</h5>
                
                <p><strong>Fix by adjusting TAX amount ONLY (net_amount unchanged):</strong></p>
                <ul>
                    <li>Net Total: ${format_currency(analysis.net_total)} (unchanged ✓)</li>
                    <li>Current Tax: ${format_currency(analysis.total_taxes_and_charges)}</li>
                    <li>New Tax: ${format_currency(new_tax)} (+${format_currency(analysis.difference)})</li>
                    <li>Grand Total: ${format_currency(analysis.grand_total)} (target)</li>
                </ul>
                
                <p style="margin-top: 15px;"><strong>Option 1: Use Button (Recommended)</strong></p>
                <p>Click <strong>"Fix BR-CO-15"</strong> button from ZATCA menu</p>
                
                <p style="margin-top: 15px;"><strong>Option 2: Execute SQL Manually</strong></p>
                <div style="background: #f5f5f5; padding: 10px; border-radius: 5px; margin-top: 10px;">
                    <div style="margin-bottom: 15px;">
                        <strong>Query 1 - Update Invoice Header:</strong><br>
                        <code style="display: block; white-space: pre-wrap; font-size: 11px; color: #d63384;">
UPDATE \`tabSales Invoice\`
SET total_taxes_and_charges = ${new_tax.toFixed(2)},
    base_total_taxes_and_charges = ${new_tax.toFixed(2)}
WHERE name = '${analysis.invoice_name}';
                        </code>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <strong>Query 2 - Update Tax Line (with JSON):</strong><br>
                        <code style="display: block; white-space: pre-wrap; font-size: 11px; color: #d63384;">
UPDATE \`tabSales Taxes and Charges\`
SET tax_amount = ${new_tax.toFixed(2)},
    base_tax_amount = ${new_tax.toFixed(2)},
    total = ${analysis.grand_total.toFixed(2)},
    base_total = ${analysis.grand_total.toFixed(2)},
    item_wise_tax_detail = '{"${item_code}":[${tax_rate},${new_tax.toFixed(2)}]}'
WHERE parent = '${analysis.invoice_name}';
                        </code>
                        <small style="color: #666; display: block; margin-top: 5px;">
                            ⚠️ Important: Updates item_wise_tax_detail JSON with new tax value
                        </small>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <strong>Query 3 - Update First Item (net_amount unchanged):</strong><br>
                        <code style="display: block; white-space: pre-wrap; font-size: 11px; color: #d63384;">
UPDATE \`tabSales Invoice Item\`
SET tax_amount = ${item_new_tax.toFixed(2)},
    total_amount = ${item_new_total.toFixed(2)}
WHERE name = '${item_name}';
                        </code>
                        <small style="color: #666; display: block; margin-top: 5px;">
                            Item: ${item_code} | Net: ${format_currency(item_net)} (unchanged) | 
                            Tax: ${format_currency(item_old_tax)} → ${format_currency(item_new_tax)} | 
                            Total: ${format_currency(item_new_total)}
                        </small>
                    </div>
                </div>
                
                <div class="alert alert-warning" style="margin-top: 10px;">
                    <strong>Important Rules:</strong>
                    <ul style="margin-bottom: 0;">
                        <li>✓ net_amount stays unchanged (${format_currency(analysis.net_total)})</li>
                        <li>✓ tax_amount adjusted by ${format_currency(analysis.difference)}</li>
                        <li>✓ total_amount = net_amount + new_tax_amount</li>
                        <li>✓ item_wise_tax_detail JSON updated with new tax value</li>
                    </ul>
                </div>
            </div>
        `;
    }
    
    let html = `
        <div style="padding: 15px;">
            <h4>Analysis Result</h4>
            
            <div class="alert alert-info" style="margin-bottom: 15px;">
                <strong>Detection Method:</strong> ${analysis.detection_method || 'grand_total - (net_total + total_taxes_and_charges)'}
            </div>
            
            <table class="table table-bordered">
                <tr>
                    <td><b>Invoice:</b></td>
                    <td>${analysis.invoice_name}</td>
                </tr>
                <tr>
                    <td><b>Net Total:</b></td>
                    <td>${format_currency(analysis.net_total)}</td>
                </tr>
                <tr>
                    <td><b>Total Taxes and Charges:</b></td>
                    <td>${format_currency(analysis.total_taxes_and_charges)}</td>
                </tr>
                <tr>
                    <td><b>Calculated Total (Net + Tax):</b></td>
                    <td>${format_currency(analysis.calculated_total)}</td>
                </tr>
                <tr>
                    <td><b>Grand Total (Stored):</b></td>
                    <td>${format_currency(analysis.grand_total)}</td>
                </tr>
                <tr>
                    <td><b>Difference:</b></td>
                    <td style="color: ${analysis.has_issue ? 'red' : 'green'}; font-weight: bold;">
                        ${format_currency(analysis.difference)}
                    </td>
                </tr>
                <tr>
                    <td><b>Status:</b></td>
                    <td>
                        <span class="indicator ${analysis.has_issue ? 'red' : 'green'}">
                            ${analysis.has_issue ? 'Has Rounding Issue' : 'Correct'}
                        </span>
                    </td>
                </tr>
            </table>
            
            ${analysis.has_issue ? `
                <div class="alert alert-warning" style="margin-top: 15px;">
                    <strong>Rounding Error Detected:</strong> Difference is ${format_currency(analysis.difference)} (less than 0.10 SAR)
                </div>
            ` : ''}
            
            <h5 style="margin-top: 20px;">Items Details:</h5>
            <table class="table table-bordered table-sm">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Item</th>
                        <th>Qty</th>
                        <th>Net</th>
                        <th>Tax</th>
                        <th>Calculated</th>
                        <th>Stored</th>
                        <th>Diff</th>
                    </tr>
                </thead>
                <tbody>
                    ${analysis.items_analysis.map(item => `
                        <tr style="${item.has_issue ? 'background-color: #fff3cd;' : ''}">
                            <td>${item.idx || ''}</td>
                            <td>${item.item_code}</td>
                            <td>${item.qty}</td>
                            <td>${format_currency(item.net_amount)}</td>
                            <td>${format_currency(item.tax_amount)} (${item.tax_rate}%)</td>
                            <td>${format_currency(item.calculated_total)}</td>
                            <td>${format_currency(item.stored_total)}</td>
                            <td style="color: ${item.has_issue ? 'red' : 'green'};">
                                ${format_currency(item.difference)}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            
            ${analysis.problematic_items_count > 0 ? `
                <div class="alert alert-warning" style="margin-top: 15px;">
                    <strong>Warning:</strong> Found ${analysis.problematic_items_count} item(s) with rounding issues
                </div>
            ` : ''}
            
            ${solution_html}
        </div>
    `;
    
    frappe.msgprint({
        title: __('Invoice Analysis'),
        message: html,
        indicator: analysis.has_issue ? 'orange' : 'green',
        wide: true
    });
}

/**
 * Format currency
 */
function format_currency(value) {
    return frappe.format(value, {fieldtype: 'Currency'});
}

// ============================================
// NEW PHASE 3: BR-CO-16 Item-Level Discrepancy Detection
// ============================================

/**
 * Analyze item-level discrepancy (BR-CO-16)
 * Detects when item.amount doesn't match (item.net_amount + item.tax_amount)
 */
function analyze_item_discrepancy(frm) {
    frappe.show_alert({
        message: __('Analyzing item-level discrepancies...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'zatca_fix.api.analyze_item_level_discrepancy',
        args: {
            invoice_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                show_item_analysis_dialog(r.message, frm);
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.message || __('Analysis failed'),
                    indicator: 'red'
                });
            }
        }
    });
}

/**
 * Fix item-level discrepancy (BR-CO-16)
 */
function fix_item_discrepancy(frm) {
    frappe.confirm(
        __('Do you want to fix item-level discrepancies in this invoice?<br><br>' +
           '<b>Issue:</b> Item amounts don\'t match (net + tax)<br>' +
           '<b>Method:</b> Adjust item.amount to equal (item.net_amount + item.tax_amount)<br>' +
           '<b>Note:</b> This fixes internal item inconsistencies that cause ZATCA rejection.'),
        function() {
            execute_item_fix(frm);
        }
    );
}

/**
 * Execute item-level fix
 */
function execute_item_fix(frm) {
    frappe.show_alert({
        message: __('Fixing item discrepancies...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'zatca_fix.api.fix_item_level_discrepancy',
        args: {
            invoice_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: __('Item discrepancies fixed successfully!'),
                    indicator: 'green'
                });
                
                show_item_fix_result(r.message);
                
                setTimeout(function() {
                    frm.reload_doc();
                }, 1500);
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.message || __('Fix failed'),
                    indicator: 'red'
                });
            }
        }
    });
}

/**
 * Show item analysis dialog
 */
function show_item_analysis_dialog(analysis, frm) {
    let solution_html = '';
    
    if (analysis.has_item_discrepancy) {
        solution_html = `
            <div class="alert alert-danger" style="margin-top: 20px;">
                <h5><i class="fa fa-exclamation-triangle"></i> Item-Level Discrepancy Detected (BR-CO-16)</h5>
                
                <p><strong>Problem:</strong></p>
                <ul>
                    <li>Found ${analysis.problematic_items_count} item(s) with internal inconsistency</li>
                    <li>Total discrepancy: ${format_currency(analysis.total_discrepancy)}</li>
                </ul>
                
                <p style="margin-top: 15px;"><strong>Solution:</strong></p>
                <p>Click <strong>"Fix BR-CO-16 (Items)"</strong> button to adjust item amounts</p>
                
                <div style="background: #f5f5f5; padding: 10px; border-radius: 5px; margin-top: 10px;">
                    <strong>Items that will be fixed:</strong>
                    <ul style="margin-bottom: 0;">
                        ${analysis.problematic_items.map(item => `
                            <li>
                                <strong>${item.item_code}:</strong> 
                                Stored: ${format_currency(item.stored_amount)} | 
                                Should be: ${format_currency(item.calculated_amount)} 
                                (Net: ${format_currency(item.net_amount)} + Tax: ${format_currency(item.tax_amount)})
                                <br><span style="color: red;">Difference: ${format_currency(item.difference)}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            </div>
        `;
    }
    
    let html = `
        <div style="padding: 15px;">
            <h4>Item-Level Discrepancy Analysis (BR-CO-16)</h4>
            
            <div class="alert alert-info" style="margin-bottom: 15px;">
                <strong>Detection Method:</strong> ${analysis.detection_method}
            </div>
            
            <table class="table table-bordered">
                <tr>
                    <td><b>Invoice:</b></td>
                    <td>${analysis.invoice_name}</td>
                </tr>
                <tr>
                    <td><b>Problematic Items:</b></td>
                    <td>${analysis.problematic_items_count}</td>
                </tr>
                <tr>
                    <td><b>Total Discrepancy:</b></td>
                    <td style="color: ${analysis.has_item_discrepancy ? 'red' : 'green'}; font-weight: bold;">
                        ${format_currency(analysis.total_discrepancy)}
                    </td>
                </tr>
                <tr>
                    <td><b>Status:</b></td>
                    <td>
                        <span class="indicator ${analysis.has_item_discrepancy ? 'red' : 'green'}">
                            ${analysis.has_item_discrepancy ? 'Discrepancy Found' : 'All Items OK'}
                        </span>
                    </td>
                </tr>
            </table>
            
            <h5 style="margin-top: 20px;">Items Details:</h5>
            <table class="table table-bordered table-sm">
                <thead>
                    <tr>
                        <th>Item Code</th>
                        <th>Qty</th>
                        <th>Stored Amount</th>
                        <th>Net Amount</th>
                        <th>Tax Amount</th>
                        <th>Calculated</th>
                        <th>Difference</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${analysis.items_analysis.map(item => `
                        <tr style="${item.has_discrepancy ? 'background-color: #f8d7da;' : ''}">
                            <td>${item.item_code}</td>
                            <td>${item.qty}</td>
                            <td>${format_currency(item.stored_amount)}</td>
                            <td>${format_currency(item.net_amount)}</td>
                            <td>${format_currency(item.tax_amount)}</td>
                            <td>${format_currency(item.calculated_amount)}</td>
                            <td style="color: ${item.has_discrepancy ? 'red' : 'green'};">
                                ${format_currency(item.difference)}
                            </td>
                            <td>
                                <span class="indicator ${item.has_discrepancy ? 'red' : 'green'}">
                                    ${item.has_discrepancy ? 'Issue' : 'OK'}
                                </span>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            
            ${solution_html}
        </div>
    `;
    
    frappe.msgprint({
        title: __('Item-Level Analysis'),
        message: html,
        indicator: analysis.has_item_discrepancy ? 'red' : 'green',
        wide: true
    });
}

/**
 * Show item fix result
 */
function show_item_fix_result(result) {
    let html = `
        <div style="padding: 15px;">
            <div class="alert alert-success">
                <strong>Item Discrepancies Fixed Successfully!</strong>
            </div>
            
            <table class="table table-bordered">
                <tr>
                    <td><b>Invoice:</b></td>
                    <td>${result.invoice_name}</td>
                </tr>
                <tr>
                    <td><b>Items Fixed:</b></td>
                    <td>${result.items_fixed}</td>
                </tr>
                <tr>
                    <td><b>Total Adjustment:</b></td>
                    <td>${format_currency(result.total_adjustment)}</td>
                </tr>
            </table>
            
            <div class="alert alert-info" style="margin-top: 15px;">
                <strong>What was fixed:</strong>
                <ul style="margin-bottom: 0;">
                    ${result.fixed_items.map(item => `
                        <li>
                            <strong>${item.item_code}:</strong> 
                            ${format_currency(item.old_amount)} → ${format_currency(item.new_amount)}
                            (adjustment: ${format_currency(item.adjustment)})
                        </li>
                    `).join('')}
                </ul>
            </div>
            
            <p style="margin-top: 15px; color: #666;">
                <i class="fa fa-check-circle"></i>
                Item amounts now match (net_amount + tax_amount)
            </p>
        </div>
    `;
    
    frappe.msgprint({
        title: __('Item Fix Result'),
        message: html,
        indicator: 'green',
        wide: true
    });
}

/**
 * Fix all issues in one click
 */
function fix_all_issues(frm) {
    frappe.confirm(
        __('Do you want to fix ALL detected issues in this invoice?<br><br>' +
           '<b>This will automatically:</b><br>' +
           '1. Fix item-level discrepancies (BR-CO-16)<br>' +
           '2. Synchronize JSON with actual values (BR-CO-14)<br>' +
           '3. Adjust tax to match grand total (BR-CO-15)<br><br>' +
           '<b>Note:</b> Issues will be fixed in the correct sequence.'),
        function() {
            execute_fix_all(frm);
        }
    );
}

/**
 * Execute fix all
 */
function execute_fix_all(frm) {
    frappe.show_alert({
        message: __('Fixing all issues...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'zatca_fix.api.fix_all_issues',
        args: {
            invoice_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: __('All issues fixed successfully!'),
                    indicator: 'green'
                });
                
                show_fix_all_result(r.message);
                
                setTimeout(function() {
                    frm.reload_doc();
                }, 2000);
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.message || __('Fix failed'),
                    indicator: 'red'
                });
            }
        }
    });
}

/**
 * Show fix all result
 */
function show_fix_all_result(result) {
    let html = `
        <div style="padding: 15px;">
            <div class="alert alert-success">
                <strong>🎉 All Issues Fixed Successfully!</strong>
            </div>
            
            <table class="table table-bordered">
                <tr>
                    <td><b>Invoice:</b></td>
                    <td>${result.invoice_name}</td>
                </tr>
                <tr>
                    <td><b>Fixes Applied:</b></td>
                    <td>${result.fixes_count}</td>
                </tr>
            </table>
            
            <h5 style="margin-top: 20px;">Fixes Applied:</h5>
            <div class="alert alert-info">
                <ul style="margin-bottom: 0;">
                    ${result.fixes_applied.map((fix, index) => `
                        <li>
                            <strong>${index + 1}. ${fix.title} (${fix.code})</strong>
                            ${fix.items_fixed ? `<br>Items fixed: ${fix.items_fixed}` : ''}
                            ${fix.adjustment ? `<br>Adjustment: ${format_currency(fix.adjustment)}` : ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
            
            <div class="alert alert-success" style="margin-top: 15px;">
                <i class="fa fa-check-circle"></i>
                <strong>Invoice is now ready for ZATCA submission!</strong>
            </div>
        </div>
    `;
    
    frappe.msgprint({
        title: __('Fix All Result'),
        message: html,
        indicator: 'green',
        wide: true
    });
}

// ============================================
// NEW PHASE 2: BR-CO-14 JSON Discrepancy Detection
// ============================================

/**
 * Analyze JSON discrepancy (BR-CO-14)
 * Detects when item_wise_tax_detail JSON doesn't match actual item tax amounts
 */
function analyze_json_discrepancy(frm) {
    frappe.show_alert({
        message: __('Analyzing JSON discrepancy...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'zatca_fix.api.analyze_json_discrepancy',
        args: {
            invoice_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                show_json_analysis_dialog(r.message, frm);
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.message || __('Analysis failed'),
                    indicator: 'red'
                });
            }
        }
    });
}

/**
 * Fix JSON discrepancy (BR-CO-14)
 */
function fix_json_discrepancy(frm) {
    frappe.confirm(
        __('Do you want to fix the JSON discrepancy in this invoice?<br><br>' +
           '<b>Issue:</b> item_wise_tax_detail JSON doesn\'t match actual item tax amounts<br>' +
           '<b>Method:</b> Synchronize JSON with actual item tax values<br>' +
           '<b>Note:</b> This fixes BR-CO-14 error from ZATCA validation.'),
        function() {
            execute_json_fix(frm);
        }
    );
}

/**
 * Execute JSON fix
 */
function execute_json_fix(frm) {
    frappe.show_alert({
        message: __('Fixing JSON discrepancy...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'zatca_fix.api.fix_json_discrepancy',
        args: {
            invoice_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: __('JSON discrepancy fixed successfully!'),
                    indicator: 'green'
                });
                
                show_json_fix_result(r.message);
                
                setTimeout(function() {
                    frm.reload_doc();
                }, 1500);
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.message || __('Fix failed'),
                    indicator: 'red'
                });
            }
        }
    });
}

/**
 * Complete analysis (both BR-CO-15 and BR-CO-14)
 */
function analyze_complete_invoice(frm) {
    frappe.show_alert({
        message: __('Running complete analysis...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'zatca_fix.api.analyze_complete',
        args: {
            invoice_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                show_complete_analysis_dialog(r.message, frm);
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message.message || __('Analysis failed'),
                    indicator: 'red'
                });
            }
        }
    });
}

/**
 * Show JSON analysis dialog
 */
function show_json_analysis_dialog(analysis, frm) {
    let solution_html = '';
    
    if (analysis.has_json_issue) {
        solution_html = `
            <div class="alert alert-danger" style="margin-top: 20px;">
                <h5><i class="fa fa-exclamation-triangle"></i> JSON Discrepancy Detected (BR-CO-14)</h5>
                
                <p><strong>Problem:</strong></p>
                <ul>
                    <li>item_wise_tax_detail JSON contains: ${format_currency(analysis.json_total_tax)}</li>
                    <li>Actual item tax amounts sum to: ${format_currency(analysis.actual_total_tax)}</li>
                    <li>Discrepancy: ${format_currency(analysis.json_discrepancy)}</li>
                </ul>
                
                <p style="margin-top: 15px;"><strong>Solution:</strong></p>
                <p>Click <strong>"Fix BR-CO-14"</strong> button to synchronize JSON with actual values</p>
                
                <div style="background: #f5f5f5; padding: 10px; border-radius: 5px; margin-top: 10px;">
                    <strong>What will be fixed:</strong>
                    <ul style="margin-bottom: 0;">
                        ${analysis.mismatched_items.map(item => `
                            <li>
                                <strong>${item.item_code}:</strong> 
                                JSON shows ${format_currency(item.json_tax)} but actual is ${format_currency(item.actual_tax)}
                                (diff: ${format_currency(item.difference)})
                            </li>
                        `).join('')}
                    </ul>
                </div>
            </div>
        `;
    }
    
    let html = `
        <div style="padding: 15px;">
            <h4>JSON Discrepancy Analysis (BR-CO-14)</h4>
            
            <div class="alert alert-info" style="margin-bottom: 15px;">
                <strong>Detection Method:</strong> Compare item_wise_tax_detail JSON with actual item tax amounts
            </div>
            
            <table class="table table-bordered">
                <tr>
                    <td><b>Invoice:</b></td>
                    <td>${analysis.invoice_name}</td>
                </tr>
                <tr>
                    <td><b>JSON Total Tax:</b></td>
                    <td>${format_currency(analysis.json_total_tax)}</td>
                </tr>
                <tr>
                    <td><b>Actual Total Tax:</b></td>
                    <td>${format_currency(analysis.actual_total_tax)}</td>
                </tr>
                <tr>
                    <td><b>Discrepancy:</b></td>
                    <td style="color: ${analysis.has_json_issue ? 'red' : 'green'}; font-weight: bold;">
                        ${format_currency(analysis.json_discrepancy)}
                    </td>
                </tr>
                <tr>
                    <td><b>Status:</b></td>
                    <td>
                        <span class="indicator ${analysis.has_json_issue ? 'red' : 'green'}">
                            ${analysis.has_json_issue ? 'JSON Mismatch Detected' : 'JSON Correct'}
                        </span>
                    </td>
                </tr>
            </table>
            
            <h5 style="margin-top: 20px;">Item-wise Comparison:</h5>
            <table class="table table-bordered table-sm">
                <thead>
                    <tr>
                        <th>Item Code</th>
                        <th>JSON Tax</th>
                        <th>Actual Tax</th>
                        <th>Difference</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${analysis.items_comparison.map(item => `
                        <tr style="${item.has_mismatch ? 'background-color: #f8d7da;' : ''}">
                            <td>${item.item_code}</td>
                            <td>${format_currency(item.json_tax)}</td>
                            <td>${format_currency(item.actual_tax)}</td>
                            <td style="color: ${item.has_mismatch ? 'red' : 'green'};">
                                ${format_currency(item.difference)}
                            </td>
                            <td>
                                <span class="indicator ${item.has_mismatch ? 'red' : 'green'}">
                                    ${item.has_mismatch ? 'Mismatch' : 'OK'}
                                </span>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            
            ${solution_html}
        </div>
    `;
    
    frappe.msgprint({
        title: __('JSON Discrepancy Analysis'),
        message: html,
        indicator: analysis.has_json_issue ? 'red' : 'green',
        wide: true
    });
}

/**
 * Show JSON fix result
 */
function show_json_fix_result(result) {
    let html = `
        <div style="padding: 15px;">
            <div class="alert alert-success">
                <strong>JSON Discrepancy Fixed Successfully!</strong>
            </div>
            
            <table class="table table-bordered">
                <tr>
                    <td><b>Invoice:</b></td>
                    <td>${result.invoice_name}</td>
                </tr>
                <tr>
                    <td><b>Items Fixed:</b></td>
                    <td>${result.items_fixed}</td>
                </tr>
                <tr>
                    <td><b>Old JSON Total:</b></td>
                    <td>${format_currency(result.old_json_total)}</td>
                </tr>
                <tr>
                    <td><b>New JSON Total:</b></td>
                    <td>${format_currency(result.new_json_total)}</td>
                </tr>
            </table>
            
            <div class="alert alert-info" style="margin-top: 15px;">
                <strong>What was fixed:</strong>
                <ul style="margin-bottom: 0;">
                    ${result.fixed_items.map(item => `
                        <li>
                            <strong>${item.item_code}:</strong> 
                            ${format_currency(item.old_json_tax)} → ${format_currency(item.new_json_tax)}
                        </li>
                    `).join('')}
                </ul>
            </div>
            
            <p style="margin-top: 15px; color: #666;">
                <i class="fa fa-check-circle"></i>
                item_wise_tax_detail JSON now matches actual item tax amounts
            </p>
        </div>
    `;
    
    frappe.msgprint({
        title: __('JSON Fix Result'),
        message: html,
        indicator: 'green',
        wide: true
    });
}

/**
 * Show complete analysis dialog (all three issues)
 */
function show_complete_analysis_dialog(analysis, frm) {
    let issues_html = '';
    let recommendations_html = '';
    
    // Build issues section
    if (analysis.issues_found && analysis.issues_found.length > 0) {
        issues_html = `
            <div class="alert alert-danger" style="margin-top: 15px;">
                <h5><i class="fa fa-exclamation-triangle"></i> Issues Detected (${analysis.issues_found.length}):</h5>
                <table class="table table-sm" style="margin-top: 10px; background: white;">
                    <thead>
                        <tr>
                            <th>Code</th>
                            <th>Issue</th>
                            <th>Severity</th>
                            <th>Impact</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${analysis.issues_found.map(issue => `
                            <tr>
                                <td><strong>${issue.code}</strong></td>
                                <td>${issue.title}<br><small>${issue.description}</small></td>
                                <td>
                                    <span class="indicator ${issue.severity === 'high' ? 'red' : 'orange'}">
                                        ${issue.severity.toUpperCase()}
                                    </span>
                                </td>
                                <td><small>${issue.impact}</small></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
        
        // Build recommendations section
        recommendations_html = `
            <div class="alert alert-info" style="margin-top: 15px;">
                <h5><i class="fa fa-lightbulb-o"></i> Recommended Fix Sequence:</h5>
                <ol style="margin-bottom: 0;">
                    ${analysis.recommendations.map(rec => `
                        <li>
                            <strong>${rec.action}</strong>
                            <br><small>Button: <code>${rec.button}</code></small>
                            <br><small style="color: #666;">${rec.reason}</small>
                        </li>
                    `).join('')}
                </ol>
                <div style="margin-top: 15px; padding: 10px; background: #d1ecf1; border-radius: 5px;">
                    <strong>💡 Quick Fix:</strong> Click <strong>"🔧 Fix All Issues"</strong> button to fix everything automatically in the correct sequence!
                </div>
            </div>
        `;
    } else {
        issues_html = `
            <div class="alert alert-success" style="margin-top: 15px;">
                <h5><i class="fa fa-check-circle"></i> All Checks Passed!</h5>
                <p style="margin-bottom: 0;">This invoice is ready for ZATCA submission. No issues detected.</p>
            </div>
        `;
    }
    
    let status_color = analysis.status === 'all_clear' ? 'green' : 'red';
    let status_text = analysis.summary.invoice_status;
    
    let html = `
        <div style="padding: 15px;">
            <h4>🔍 Complete ZATCA Analysis</h4>
            
            <div class="alert alert-${analysis.status === 'all_clear' ? 'success' : 'warning'}" style="margin-bottom: 15px;">
                <table class="table table-borderless" style="margin-bottom: 0;">
                    <tr>
                        <td style="width: 30%;"><strong>Invoice:</strong></td>
                        <td>${analysis.invoice_name}</td>
                    </tr>
                    <tr>
                        <td><strong>Status:</strong></td>
                        <td>
                            <span class="indicator ${status_color}" style="font-size: 14px;">
                                ${status_text}
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Total Issues:</strong></td>
                        <td>${analysis.summary.total_issues} (${analysis.summary.critical_issues} critical)</td>
                    </tr>
                </table>
            </div>
            
            ${issues_html}
            ${recommendations_html}
            
            <h5 style="margin-top: 25px; border-top: 2px solid #ddd; padding-top: 15px;">📊 Detailed Results:</h5>
            
            <!-- BR-CO-16: Item-Level Check -->
            <div style="margin-top: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                <h6>
                    <span class="indicator ${analysis.br_co_16.has_item_discrepancy ? 'red' : 'green'}"></span>
                    1. BR-CO-16: Item-Level Consistency
                </h6>
                <table class="table table-bordered table-sm">
                    <tr>
                        <td><b>Detection:</b></td>
                        <td><small>${analysis.br_co_16.detection_method}</small></td>
                    </tr>
                    <tr>
                        <td><b>Problematic Items:</b></td>
                        <td>${analysis.br_co_16.problematic_items_count}</td>
                    </tr>
                    <tr>
                        <td><b>Total Discrepancy:</b></td>
                        <td style="color: ${analysis.br_co_16.has_item_discrepancy ? 'red' : 'green'};">
                            ${format_currency(analysis.br_co_16.total_discrepancy)}
                        </td>
                    </tr>
                    <tr>
                        <td><b>Status:</b></td>
                        <td>
                            <span class="indicator ${analysis.br_co_16.has_item_discrepancy ? 'red' : 'green'}">
                                ${analysis.br_co_16.has_item_discrepancy ? 'Issue Found' : 'OK'}
                            </span>
                        </td>
                    </tr>
                </table>
            </div>
            
            <!-- BR-CO-14: JSON Check -->
            <div style="margin-top: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                <h6>
                    <span class="indicator ${analysis.br_co_14.has_json_issue ? 'red' : 'green'}"></span>
                    2. BR-CO-14: JSON Discrepancy
                </h6>
                <table class="table table-bordered table-sm">
                    <tr>
                        <td><b>Detection:</b></td>
                        <td><small>${analysis.br_co_14.detection_method}</small></td>
                    </tr>
                    <tr>
                        <td><b>JSON Total Tax:</b></td>
                        <td>${format_currency(analysis.br_co_14.json_total_tax)}</td>
                    </tr>
                    <tr>
                        <td><b>Actual Total Tax:</b></td>
                        <td>${format_currency(analysis.br_co_14.actual_total_tax)}</td>
                    </tr>
                    <tr>
                        <td><b>Discrepancy:</b></td>
                        <td style="color: ${analysis.br_co_14.has_json_issue ? 'red' : 'green'};">
                            ${format_currency(analysis.br_co_14.json_discrepancy)}
                        </td>
                    </tr>
                    <tr>
                        <td><b>Status:</b></td>
                        <td>
                            <span class="indicator ${analysis.br_co_14.has_json_issue ? 'red' : 'green'}">
                                ${analysis.br_co_14.has_json_issue ? 'Issue Found' : 'OK'}
                            </span>
                        </td>
                    </tr>
                </table>
            </div>
            
            <!-- BR-CO-15: Rounding Check -->
            <div style="margin-top: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                <h6>
                    <span class="indicator ${analysis.br_co_15.has_issue ? 'red' : 'green'}"></span>
                    3. BR-CO-15: Rounding Issue
                </h6>
                <table class="table table-bordered table-sm">
                    <tr>
                        <td><b>Detection:</b></td>
                        <td><small>${analysis.br_co_15.detection_method}</small></td>
                    </tr>
                    <tr>
                        <td><b>Net Total:</b></td>
                        <td>${format_currency(analysis.br_co_15.net_total)}</td>
                    </tr>
                    <tr>
                        <td><b>Tax Total:</b></td>
                        <td>${format_currency(analysis.br_co_15.total_taxes_and_charges)}</td>
                    </tr>
                    <tr>
                        <td><b>Grand Total:</b></td>
                        <td>${format_currency(analysis.br_co_15.grand_total)}</td>
                    </tr>
                    <tr>
                        <td><b>Difference:</b></td>
                        <td style="color: ${analysis.br_co_15.has_issue ? 'red' : 'green'};">
                            ${format_currency(analysis.br_co_15.difference)}
                        </td>
                    </tr>
                    <tr>
                        <td><b>Status:</b></td>
                        <td>
                            <span class="indicator ${analysis.br_co_15.has_issue ? 'red' : 'green'}">
                                ${analysis.br_co_15.has_issue ? 'Issue Found' : 'OK'}
                            </span>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    `;
    
    frappe.msgprint({
        title: __('Complete ZATCA Analysis'),
        message: html,
        indicator: status_color,
        wide: true
    });
}
