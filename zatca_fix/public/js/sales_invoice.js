// ZATCA Fix - safe XML-only correction layer for RUKN KSA Compliance.
// This script never changes submitted invoice tax/accounting values.

frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        if (frm.doc.docstatus !== 1) return;

        frm.add_custom_button(__('فحص توافق XML'), () => analyze_zatca_fix(frm), __('ZATCA Fix'));
        frm.add_custom_button(__('حالة التصحيح'), () => show_patch_status(), __('ZATCA Fix'));
        frm.add_custom_button(__('إصلاح وإعادة إرسال المرفوض'), () => retry_rejected(frm), __('ZATCA Fix'));
    }
});

function show_patch_status() {
    frappe.call({
        method: 'zatca_fix.api.get_patch_status',
        callback(r) {
            const data = r.message || {};
            const rules = (data.rules_covered || []).join(', ');
            frappe.msgprint({
                title: __('ZATCA Fix'),
                indicator: data.active ? 'green' : 'red',
                message: `
                    <p><b>${data.active ? __('التصحيح مفعل') : __('التصحيح غير مفعل')}</b></p>
                    <p>${__('طريقة العمل: تصحيح XML قبل التوقيع فقط، بدون تعديل قيم الفاتورة أو الضريبة أو القيود المحاسبية.')}</p>
                    <p><b>${__('القواعد المغطاة')}:</b> ${frappe.utils.escape_html(rules)}</p>
                `
            });
        }
    });
}

function analyze_zatca_fix(frm) {
    frappe.call({
        method: 'zatca_fix.api.analyze_invoice',
        args: { invoice_name: frm.doc.name },
        freeze: true,
        freeze_message: __('جاري فحص الفاتورة...'),
        callback(r) {
            const a = r.message;
            if (!a || !a.success) return;

            const rows = (a.items || []).map(item => `
                <tr>
                    <td>${item.idx || ''}</td>
                    <td>${frappe.utils.escape_html(item.item_code || '')}</td>
                    <td>${format_money(item.xml_line_net)}</td>
                    <td>${format_money(item.xml_line_tax)}</td>
                    <td>${format_money(item.expected_line_with_vat)}</td>
                    <td>${format_money(item.stored_total_amount)}</td>
                    <td>${item.line_issue ? '<span class="indicator red">فرق</span>' : '<span class="indicator green">سليم</span>'}</td>
                </tr>
            `).join('');

            frappe.msgprint({
                title: __('فحص ZATCA XML'),
                indicator: a.has_issue ? 'orange' : 'green',
                wide: true,
                message: `
                    <div style="padding:8px">
                        <div class="alert alert-info">
                            ${__('هذا الفحص لا يعدل الفاتورة. التصحيح يتم على XML الذي يولده RUKN قبل التوقيع.')}
                        </div>
                        <table class="table table-bordered">
                            <tr><td><b>${__('صافي الفاتورة')}</b></td><td>${format_money(a.net_total)}</td></tr>
                            <tr><td><b>${__('الضريبة')}</b></td><td>${format_money(a.tax_total)}</td></tr>
                            <tr><td><b>${__('الإجمالي الحالي')}</b></td><td>${format_money(a.grand_total)}</td></tr>
                            <tr><td><b>${__('الإجمالي الصحيح لـ XML')}</b></td><td>${format_money(a.expected_tax_inclusive)}</td></tr>
                            <tr><td><b>${__('فرق BT-112')}</b></td><td>${format_money(a.tax_inclusive_difference)}</td></tr>
                            <tr><td><b>${__('PayableRoundingAmount المتوقع')}</b></td><td>${format_money(a.expected_payable_rounding)}</td></tr>
                        </table>
                        <h5>${__('الأصناف')}</h5>
                        <table class="table table-bordered table-sm">
                            <thead><tr>
                                <th>#</th><th>${__('الصنف')}</th><th>${__('الصافي')}</th><th>${__('الضريبة')}</th>
                                <th>${__('الإجمالي الصحيح')}</th><th>${__('المخزن')}</th><th>${__('الحالة')}</th>
                            </tr></thead>
                            <tbody>${rows}</tbody>
                        </table>
                        <p><b>${__('القواعد التي يعالجها التطبيق')}:</b> ${(a.rules_covered || []).join(', ')}</p>
                    </div>
                `
            });
        }
    });
}

function retry_rejected(frm) {
    frappe.confirm(
        __('سيستخدم التطبيق وظيفة Fix Rejection الرسمية من RUKN لإنشاء محاولة جديدة، وسيتم تصحيح XML قبل توقيعه. لن يتم تعديل قيم الفاتورة المحاسبية. هل تريد المتابعة؟'),
        () => {
            frappe.call({
                method: 'zatca_fix.api.retry_rejected_invoice',
                args: { invoice_name: frm.doc.name },
                freeze: true,
                freeze_message: __('جاري إنشاء محاولة ZATCA مصححة...'),
                callback(r) {
                    const data = r.message || {};
                    if (!data.success) return;
                    frappe.msgprint({
                        title: __('تم إنشاء محاولة جديدة'),
                        indicator: 'green',
                        message: `
                            <p>${frappe.utils.escape_html(data.message || '')}</p>
                            <p><b>${__('السجل السابق')}:</b> ${frappe.utils.escape_html(data.old_additional_fields || '')}</p>
                            <p><b>${__('السجل الجديد')}:</b> ${frappe.utils.escape_html(data.new_additional_fields || '')}</p>
                        `
                    });
                }
            });
        }
    );
}

function format_money(value) {
    return frappe.format(value || 0, { fieldtype: 'Currency' });
}
