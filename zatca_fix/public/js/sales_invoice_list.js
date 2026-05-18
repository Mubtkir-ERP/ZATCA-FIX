frappe.listview_settings['Sales Invoice'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('إصلاح فواتير زاتكا'), function() {
            let selected_docs = listview.get_checked_items();
            if (selected_docs.length === 0) {
                frappe.msgprint(__('الرجاء تحديد فاتورة واحدة على الأقل.'));
                return;
            }

            let doc_names = selected_docs.map(doc => doc.name);
            
            frappe.confirm(
                __('هل أنت متأكد من رغبتك في إصلاح القيم الحسابية لـ {0} فواتير لتتوافق مع زاتكا؟', [doc_names.length]),
                function() {
                    frappe.call({
                        method: 'zatca_fix.api.fix_zatca_invoices',
                        args: {
                            invoices: doc_names
                        },
                        freeze: true,
                        freeze_message: __('جاري إصلاح الفواتير...'),
                        callback: function(r) {
                            if (!r.exc) {
                                frappe.msgprint(__('تم إصلاح الفواتير بنجاح! الرجاء الآن تحديث الصفحة وإعادة إرسالها لزاتكا.'));
                                listview.refresh();
                            }
                        }
                    });
                }
            );
        });
    }
};
