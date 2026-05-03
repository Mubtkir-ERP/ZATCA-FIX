// ============================================
// ZATCA Fix - Sales Invoice Client Script
// Fix BR-CO-15 rounding issues
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
 * Fix rounding issue
 */
function fix_zatca_rounding_issue(frm) {
    frappe.confirm(
        __('Do you want to fix the rounding issue in this invoice?<br><br>' +
           '<b>Note:</b> This will update the database directly without canceling submission.<br>' +
           'This action is safe and will not affect accounting entries.'),
        function() {
            analyze_and_fix_invoice(frm);
        }
    );
}

/**
 * Analyze invoice using simplified detection method
 * Detection: Difference = grand_total - (net_total + total_taxes_and_charges)
 * Rounding error if: Difference != 0 AND abs(Difference) < 0.10
 */
function analyze_invoice(frm) {
    // Simple detection method
    let net_total = flt(frm.doc.net_total, 2);
    let total_taxes = flt(frm.doc.total_taxes_and_charges, 2);
    let grand_total = flt(frm.doc.grand_total, 2);
    
    let calculated_total = flt(net_total + total_taxes, 2);
    let difference = flt(grand_total - calculated_total, 2);
    
    // Rounding error if difference is not zero but less than 0.10
    let has_issue = (difference !== 0) && (Math.abs(difference) < 0.10);
    
    // Detailed items analysis for fixing
    let items_details = [];
    
    frm.doc.items.forEach(function(item) {
        let net = flt(item.net_amount, 2);
        let tax = flt(item.tax_amount, 2);
        let calculated = flt(net + tax, 2);
        let stored = flt(item.amount, 2);
        let diff = flt(calculated - stored, 2);
        
        items_details.push({
            name: item.name,
            idx: item.idx,
            item_code: item.item_code,
            item_name: item.item_name,
            qty: item.qty,
            rate: flt(item.rate, 2),
            net_amount: net,
            tax_rate: flt(item.tax_rate, 2),
            tax_amount: tax,
            calculated_total: calculated,
            stored_total: stored,
            difference: diff,
            has_issue: Math.abs(diff) > 0.001
        });
    });
    
    let problematic_items = items_details.filter(item => item.has_issue);
    
    return {
        invoice_name: frm.doc.name,
        detection_method: 'grand_total - (net_total + total_taxes_and_charges)',
        net_total: net_total,
        total_taxes_and_charges: total_taxes,
        calculated_total: calculated_total,
        grand_total: grand_total,
        difference: difference,
        has_issue: has_issue,
        items_count: items_details.length,
        items_details: items_details,
        problematic_items: problematic_items,
        problematic_items_count: problematic_items.length
    };
}

/**
 * Analyze and fix invoice
 */
function analyze_and_fix_invoice(frm) {
    frappe.show_alert({
        message: __('Analyzing invoice...'),
        indicator: 'blue'
    });

    let analysis = analyze_invoice(frm);
    
    console.log('=== Invoice Analysis ===');
    console.log('Detection Method:', analysis.detection_method);
    console.log('Net Total:', analysis.net_total);
    console.log('Total Taxes:', analysis.total_taxes_and_charges);
    console.log('Calculated Total:', analysis.calculated_total);
    console.log('Grand Total:', analysis.grand_total);
    console.log('Difference:', analysis.difference);
    console.log('Has Issue:', analysis.has_issue);
    console.log('Problematic Items:', analysis.problematic_items);
    
    if (!analysis.has_issue) {
        frappe.msgprint({
            title: __('No Issue'),
            message: __('Invoice is correct and does not need fixing'),
            indicator: 'green'
        });
        return;
    }
    
    frappe.show_alert({
        message: __('Rounding difference detected: {0} SAR', [analysis.difference]),
        indicator: 'orange'
    });
    
    let sql_queries = build_fix_queries(analysis);
    execute_fix(frm, sql_queries, analysis);
}

/**
 * Build SQL queries for fixing
 */
function build_fix_queries(analysis) {
    let queries = [];
    
    if (analysis.problematic_items.length > 0) {
        // Fix items that have rounding issues
        analysis.problematic_items.forEach(function(item) {
            let correct_amount = item.calculated_total;
            
            queries.push({
                query: `UPDATE \`tabSales Invoice Item\` 
                        SET amount = ${correct_amount}, 
                            base_amount = ${correct_amount}
                        WHERE name = '${item.name}'`,
                item_name: item.name,
                item_code: item.item_code,
                old_amount: item.stored_total,
                new_amount: correct_amount
            });
        });
    } else {
        // No problematic items, adjust last item with the difference
        let last_item = analysis.items_details[analysis.items_details.length - 1];
        let adjustment = analysis.difference;
        let new_amount = flt(last_item.stored_total + adjustment, 2);
        
        queries.push({
            query: `UPDATE \`tabSales Invoice Item\` 
                    SET amount = ${new_amount}, 
                        base_amount = ${new_amount}
                    WHERE name = '${last_item.name}'`,
            item_name: last_item.name,
            item_code: last_item.item_code,
            old_amount: last_item.stored_total,
            new_amount: new_amount
        });
    }
    
    return queries;
}

/**
 * Execute fix
 */
function execute_fix(frm, sql_queries, analysis) {
    let completed = 0;
    let total = sql_queries.length;
    let errors = [];
    
    sql_queries.forEach(function(sql_obj, index) {
        frappe.call({
            method: 'zatca_fix.api.execute_sql',
            args: {
                query: sql_obj.query
            },
            callback: function(r) {
                completed++;
                
                if (r.exc || (r.message && !r.message.success)) {
                    console.error('Failed to execute:', sql_obj.item_code, r.exc);
                    errors.push({
                        item: sql_obj.item_code,
                        error: r.exc || r.message.message
                    });
                } else {
                    console.log('✓ Fixed:', sql_obj.item_code, 'from', sql_obj.old_amount, 'to', sql_obj.new_amount);
                }
                
                if (completed === total) {
                    if (errors.length > 0) {
                        frappe.msgprint({
                            title: __('Error'),
                            message: __('Failed to fix some items: {0}', [errors.map(e => e.item).join(', ')]),
                            indicator: 'red'
                        });
                    } else {
                        frappe.show_alert({
                            message: __('Invoice fixed successfully!'),
                            indicator: 'green'
                        });
                        
                        show_fix_result(analysis, sql_queries);
                        
                        setTimeout(function() {
                            frm.reload_doc();
                        }, 1500);
                    }
                }
            }
        });
    });
}

/**
 * Show analysis dialog
 */
function show_analysis_dialog(analysis, frm) {
    let sql_queries = analysis.has_issue ? build_fix_queries(analysis) : [];
    let solution_html = '';
    
    if (analysis.has_issue) {
        solution_html = `
            <div class="alert alert-info" style="margin-top: 20px;">
                <h5><i class="fa fa-wrench"></i> Solution:</h5>
                <p><strong>Option 1: Use Button (Recommended)</strong></p>
                <p>Click <strong>"Fix BR-CO-15"</strong> button from ZATCA menu</p>
                
                <p style="margin-top: 15px;"><strong>Option 2: Execute SQL Manually</strong></p>
                <div style="background: #f5f5f5; padding: 10px; border-radius: 5px; margin-top: 10px;">
                    ${sql_queries.map((q, idx) => `
                        <div style="margin-bottom: 10px;">
                            <strong>Query ${idx + 1}:</strong><br>
                            <code style="display: block; white-space: pre-wrap; font-size: 11px; color: #d63384;">
${q.query}
                            </code>
                            <small style="color: #666;">
                                Item: ${q.item_code} | From ${format_currency(q.old_amount)} to ${format_currency(q.new_amount)}
                            </small>
                        </div>
                    `).join('')}
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
 * Show fix result
 */
function show_fix_result(analysis, sql_queries) {
    let html = `
        <div style="padding: 15px;">
            <div class="alert alert-success">
                <strong>Fixed Successfully!</strong>
            </div>
            
            <table class="table table-bordered">
                <tr>
                    <td><b>Fixed Difference:</b></td>
                    <td>${format_currency(analysis.difference)}</td>
                </tr>
                <tr>
                    <td><b>Modified Items:</b></td>
                    <td>${sql_queries.length}</td>
                </tr>
            </table>
            
            <h5 style="margin-top: 20px;">Modified Items:</h5>
            <table class="table table-bordered table-sm">
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Old Value</th>
                        <th>New Value</th>
                        <th>Adjustment</th>
                    </tr>
                </thead>
                <tbody>
                    ${sql_queries.map(item => `
                        <tr>
                            <td>${item.item_code}</td>
                            <td>${format_currency(item.old_amount)}</td>
                            <td>${format_currency(item.new_amount)}</td>
                            <td style="color: green;">
                                ${format_currency(item.new_amount - item.old_amount)}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            
            <p style="margin-top: 15px; color: #666;">
                <i class="fa fa-info-circle"></i>
                Database updated directly without canceling submission.
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
 * Format currency
 */
function format_currency(value) {
    return frappe.format(value, {fieldtype: 'Currency'});
}

/**
 * Float helper
 */
function flt(value, precision = 2) {
    if (value === null || value === undefined || value === '') {
        return 0;
    }
    let multiplier = Math.pow(10, precision);
    return Math.round(parseFloat(value) * multiplier) / multiplier;
}
