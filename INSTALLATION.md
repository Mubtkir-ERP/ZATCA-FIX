# ZATCA Fix - Installation Guide

## 🚀 Quick Installation

### Step 1: Install the App

```bash
# Navigate to bench directory
cd /path/to/frappe-bench

# Install the app on your site
bench --site your-site.com install-app zatca_fix

# Build assets
bench build --app zatca_fix

# Restart
bench restart
```

### Step 2: Verify Installation

1. Open ERPNext
2. Go to any submitted Sales Invoice
3. You should see **ZATCA** menu with two options:
   - Analyze BR-CO-15
   - Fix BR-CO-15

## ✅ That's it!

No additional configuration needed. The app is ready to use.

## 📋 Usage

### Analyze Invoice:
```
1. Open submitted Sales Invoice
2. Click ZATCA → Analyze BR-CO-15
3. View detailed analysis
```

### Fix Invoice:
```
1. Open submitted Sales Invoice
2. Click ZATCA → Fix BR-CO-15
3. Confirm the action
4. Done!
```

## 🔧 Troubleshooting

### Buttons not showing?
```bash
# Clear cache
bench --site your-site.com clear-cache

# Rebuild
bench build --app zatca_fix

# Restart
bench restart
```

### Permission errors?
```bash
# Make sure you have write permission on Sales Invoice
```

## 📞 Support

For issues, please check the README.md file or contact support.
