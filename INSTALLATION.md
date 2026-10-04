# Installation / Upgrade

## Existing installation

Replace the app code with this version, then run:

```bash
bench --site YOUR-SITE migrate
bench build --app zatca_fix
bench clear-cache
bench restart
```

If you use production workers/scheduler, make sure all workers have restarted so the `before_job` runtime patch is loaded.

## Verification

Open a submitted Sales Invoice and choose:

**ZATCA Fix → حالة التصحيح**

It should show that the XML-only patch is active.

Then choose:

**ZATCA Fix → فحص توافق XML**

No Sales Invoice accounting value is changed by these actions.

## Rejected invoice

For an invoice whose latest RUKN `Sales Invoice Additional Fields` status is `Rejected`, use:

**ZATCA Fix → إصلاح وإعادة إرسال المرفوض**

This delegates the retry to RUKN's official `Fix Rejection` backend. RUKN creates the new attempt; ZATCA Fix only normalizes the newly generated unsigned XML before signing.
