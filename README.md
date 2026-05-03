# ZATCA Fix

Fix ZATCA BR-CO-15 rounding issues in Sales Invoices for ERPNext.

## Features

- ✅ **Analyze Invoices** - Detect rounding issues in submitted invoices
- ✅ **Auto Fix** - Automatically fix rounding differences
- ✅ **Safe** - Updates database directly without canceling submission
- ✅ **Smart** - Identifies problematic items automatically
- ✅ **Easy** - Simple buttons in Sales Invoice form

## Installation

```bash
# Get the app
bench get-app https://github.com/yourusername/zatca_fix

# Install on site
bench --site your-site install-app zatca_fix

# Build assets
bench build --app zatca_fix

# Restart
bench restart
```

## Usage

### In Sales Invoice:

1. Open any submitted Sales Invoice
2. Click **ZATCA** menu
3. Choose:
   - **Analyze BR-CO-15** - View detailed analysis
   - **Fix BR-CO-15** - Auto-fix the issue

### What it fixes:

**Problem:** ZATCA error BR-CO-15
```
Invoice total amount with VAT (BT-112)
```

**Cause:** Rounding differences when `round_row_wise_tax` is enabled

**Solution:** Adjusts item amounts to match calculated totals

## Example

**Before Fix:**
```
Item: 102-مديني
- Net: 130.43 SAR
- Tax: 19.56 SAR
- Calculated: 150.00 SAR
- Stored: 149.99 SAR ❌
- Difference: 0.01 SAR
```

**After Fix:**
```
Item: 102-مديني
- Net: 130.43 SAR
- Tax: 19.56 SAR
- Calculated: 150.00 SAR
- Stored: 150.00 SAR ✅
- Difference: 0.00 SAR
```

## Technical Details

### Files:
- `api.py` - Python API for SQL execution and analysis
- `public/js/sales_invoice.js` - Client-side JavaScript
- `hooks.py` - App configuration

### What it modifies:
- ✅ `amount` field in Sales Invoice Item
- ✅ `base_amount` field in Sales Invoice Item
- ❌ Does NOT modify `modified` timestamp
- ❌ Does NOT affect accounting entries
- ❌ Does NOT cancel submission

### Security:
- Uses `@frappe.whitelist()` decorator
- Executes SQL via `frappe.db.sql()`
- Commits changes via `frappe.db.commit()`
- Logs errors to Error Log

## Requirements

- ERPNext v13 or higher
- Frappe Framework v13 or higher

## License

MIT

## Support

For issues and questions, please open an issue on GitHub.

## Credits

Developed for fixing ZATCA compliance issues in Saudi Arabia.
