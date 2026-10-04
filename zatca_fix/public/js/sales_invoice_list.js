frappe.listview_settings['Sales Invoice'] = {
    onload(listview) {
        listview.page.add_inner_button(__('حالة ZATCA Fix'), function () {
            frappe.call({
                method: 'zatca_fix.api.get_patch_status',
                callback(r) {
                    const data = r.message || {};
                    frappe.msgprint({
                        title: __('ZATCA Fix'),
                        indicator: data.active ? 'green' : 'red',
                        message: data.active
                            ? __('التصحيح مفعل ويعمل عند توليد XML. لا يتم تعديل الفواتير المعتمدة في قاعدة البيانات.')
                            : __('التصحيح غير مفعل. راجع سجل الأخطاء وأعد تشغيل bench بعد التحديث.')
                    });
                }
            });
        });
    }
};
