app_name = "zatca_fix"
app_title = "ZATCA Fix"
app_publisher = "Mubtkir"
app_description = "Safe XML-level compatibility fixes for RUKN KSA Compliance / ZATCA rounding validation"
app_email = ""
app_license = "MIT"

# RUKN / KSA Compliance is intentionally not modified. This app wraps its generated
# unsigned XML immediately before RUKN signs it.
required_apps = ["ksa_compliance"]

doctype_js = {
    "Sales Invoice": "public/js/sales_invoice.js",
}

doctype_list_js = {
    "Sales Invoice": "public/js/sales_invoice_list.js",
}

# Apply the wrapper to both normal web requests and background jobs. RUKN's live-sync
# and Fix Rejection paths can run in either context.
before_request = ["zatca_fix.runtime.apply_patches"]
before_job = ["zatca_fix.runtime.apply_patches"]
