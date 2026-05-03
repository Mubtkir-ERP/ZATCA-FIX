// ============================================
// ZATCA Fix - Sales Invoice Client Script
// Fix BR-CO-15 rounding issues by adjusting TAX
// ============================================

frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Add buttons only for submitted invoices
        if (frm.doc.docstatus === 1) {
            // Fix button
            frm.add_custom_button(__('Fix BR-CO-15'), function() {
                fix_zatca_rounding_issue(frm);
            }, __('ZATCA'));
            
            // Analyze button
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
