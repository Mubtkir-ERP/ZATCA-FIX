# ZATCA Fix 0.2.0

A safe compatibility layer for **RUKN / KSA Compliance** on ERPNext.

## What changed in 0.2.0

Older versions of this app attempted to fix ZATCA validation errors by changing tax and total fields directly on submitted Sales Invoices. That approach has been removed.

This version fixes the generated **unsigned UBL XML before RUKN signs it**. It does not modify RUKN source code and it does not change submitted invoice accounting values or GL entries.

## Covered arithmetic validations

- `BR-KSA-51` — line amount with VAT = line net + line VAT
- `BR-KSA-EN16931-07` — net item price = gross item price - price allowance
- `BR-CO-10` — invoice line extension total = sum of lines
- `BR-CO-11` — allowance total = sum of document allowances
- `BR-CO-14` — invoice VAT = sum of VAT category VAT amounts
- `BR-CO-15` — tax inclusive total = tax exclusive total + VAT
- `BR-CO-16` — payable = tax inclusive - prepaid + payable rounding

## How it works

`zatca_fix.runtime.apply_patches` wraps RUKN's `generate_xml_file()` at runtime. The wrapper receives the unsigned XML, normalizes only derived arithmetic fields, and returns it to RUKN. RUKN then signs and sends the corrected XML normally.

The patch is installed for both:

- web requests (`before_request`)
- background jobs (`before_job`)

This also covers RUKN's built-in **Fix Rejection** flow.

## Rejected historical invoices

Open the submitted Sales Invoice and use:

**ZATCA Fix → إصلاح وإعادة إرسال المرفوض**

The button calls RUKN's official `Fix Rejection` backend. RUKN creates a new `Sales Invoice Additional Fields` attempt and ZATCA Fix normalizes the newly generated XML before signing.

The button only works when the latest RUKN integration status is `Rejected`.

## Upgrade commands

After replacing/updating the app code:

```bash
bench --site YOUR-SITE migrate
bench build --app zatca_fix
bench clear-cache
bench restart
```

## Safety

- No direct SQL updates to submitted Sales Invoices.
- No change to `total_taxes_and_charges`, `grand_total`, item tax amounts, or GL Entries.
- RUKN remains untouched and can continue to be updated from its own Git repository.
