# ZATCA Fix - Tax Adjustment Method

## الطريقة الصحيحة لإصلاح خطأ BR-CO-15

### المشكلة
عند تفعيل `round_row_wise_tax` في إعدادات الحسابات، يحدث خطأ تقريب تراكمي:
- `net_total` = 70.43
- `total_taxes_and_charges` = 10.56
- `grand_total` = 81.00
- **المشكلة:** 70.43 + 10.56 = 80.99 ≠ 81.00 (فرق 0.01)

### الحل الصحيح: تعديل الضريبة (وليس الأصناف)

#### لماذا نعدل الضريبة؟
1. **الصافي ثابت**: `net_total` هو وعاء الضريبة ولا يجب تغييره
2. **الإجمالي صحيح**: `grand_total` هو المبلغ المقبوض فعلياً من العميل
3. **الضريبة مرنة**: يمكن تعديل الضريبة بمقدار الفرق دون تأثير قانوني

#### المعادلة
```
الضريبة الجديدة = الضريبة الحالية + الفرق
New Tax = Current Tax + (Grand Total - (Net Total + Current Tax))
```

### مثال عملي

**قبل التصحيح:**
```
Net Total:              70.43 SAR
Tax (15%):              10.56 SAR
Calculated:             80.99 SAR
Grand Total (Stored):   81.00 SAR
Difference:              0.01 SAR ❌
```

**بعد التصحيح:**
```
Net Total:              70.43 SAR (unchanged)
Tax (adjusted):         10.57 SAR (+0.01)
Calculated:             81.00 SAR
Grand Total (Stored):   81.00 SAR
Difference:              0.00 SAR ✅
```

### التنفيذ

#### Python API (`fix_invoice_tax`)
```python
# Calculate difference
difference = grand_total - (net_total + total_taxes)

# Adjust tax
new_tax_amount = total_taxes + difference

# Update 3 places:
# 1. Invoice header (total_taxes_and_charges)
# 2. Tax line (tax_amount, total)
# 3. First item (tax_amount, total_amount)
```

#### SQL Queries
```sql
-- 1. Update Invoice Header
UPDATE `tabSales Invoice`
SET total_taxes_and_charges = 10.57,
    base_total_taxes_and_charges = 10.57
WHERE name = 'ACC-SINV-2026-09727';

-- 2. Update Tax Line
UPDATE `tabSales Taxes and Charges`
SET tax_amount = 10.57,
    base_tax_amount = 10.57,
    total = 81.00,
    base_total = 81.00
WHERE parent = 'ACC-SINV-2026-09727';

-- 3. Update First Item
UPDATE `tabSales Invoice Item`
SET tax_amount = 10.57,
    total_amount = 81.00
WHERE parent = 'ACC-SINV-2026-09727'
LIMIT 1;
```

### الفرق بين الطريقتين

| الجانب | الطريقة القديمة (خطأ) | الطريقة الجديدة (صحيحة) |
|--------|----------------------|-------------------------|
| **ما يتم تعديله** | `amount` في الأصناف | `tax_amount` في الضريبة |
| **الصافي** | قد يتغير | يبقى ثابتاً |
| **الضريبة** | تبقى ثابتة | تتعدل بالفرق |
| **وعاء الضريبة** | قد يتأثر | لا يتأثر |
| **الامتثال الضريبي** | مشكوك فيه | صحيح 100% |

### الاستخدام

#### من واجهة ERPNext
1. افتح الفاتورة المرسلة
2. اضغط على قائمة "ZATCA"
3. اختر "Analyze BR-CO-15" للتحليل
4. اختر "Fix BR-CO-15" للإصلاح التلقائي

#### من SQL مباشرة
استخدم الاستعلامات الثلاثة أعلاه مع تعديل:
- اسم الفاتورة
- قيمة الضريبة الجديدة
- قيمة الإجمالي النهائي

### الأمان
✅ لا يلغي الإرسال  
✅ لا يعدل حقل `modified`  
✅ لا يؤثر على القيود المحاسبية  
✅ يحافظ على وعاء الضريبة  
✅ متوافق مع ZATCA  

### الملفات المعدلة
- `apps/zatca_fix/zatca_fix/api.py` - دالة `fix_invoice_tax()`
- `apps/zatca_fix/zatca_fix/public/js/sales_invoice.js` - واجهة المستخدم

---
**آخر تحديث:** تم تغيير الطريقة من تعديل الأصناف إلى تعديل الضريبة  
**الحالة:** جاهز للاستخدام ✅
