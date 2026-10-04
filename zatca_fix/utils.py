"""Compatibility module for older installs of ZATCA Fix.

The old implementation modified POS/Sales Invoice tax and total fields. That behavior
has been removed intentionally. ZATCA fixes are now applied only to RUKN-generated XML.
"""


def fix_pos_rounding_issues(doc, method=None):
    # Kept as a no-op so an old cached hook cannot alter accounting data after upgrade.
    return None
