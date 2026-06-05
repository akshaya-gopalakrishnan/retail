# Retail App - Public Assets & Customizations

This directory contains all custom CSS, JavaScript, and icons for the Retail app sidebar and navigation.

## 📁 File Structure

```
retail/public/
├── css/
│   ├── retail_icons.css       ← Icon styling & colors
│   └── retail_sidebar.css      ← Sidebar layout customizations
├── js/
│   ├── retail_navigation.js    ← Sidebar state & menu navigation
│   └── retail_icons.js         ← Icon initialization & mapping
└── README.md                   ← This file
```

## 🎨 Customization Guide

### 1. **Icon Styling** (`retail_icons.css`)
Controls how icons look and behave:
- **Icon sizes**: Change `width` and `height` values
- **Icon colors**: Modify stroke colors per module (Sales, Purchases, Stocks, etc.)
- **Hover effects**: Update `transform` and `transition` properties
- **Responsive sizing**: Adjust `@media` rules for different screen sizes

**Example - Change Sales icon color:**
```css
.sales-icon {
    stroke: #3b82f6; /* Change this hex color */
}
```

### 2. **Icon Mapping** (`retail_icons.js`)
Maps sidebar labels to Lucide icon names:
- Update the `ICON_MAP` object to change which icon appears for each menu
- Icon names available at: https://lucide.dev/

**Example - Add new icon:**
```javascript
'My New Menu': { icon: 'star', class: 'items-icon' }
```

### 3. **Sidebar Navigation** (`retail_navigation.js`)
Handles sidebar state management:
- Parent workspace selection
- Child menu highlighting
- History/back button behavior
- DOM state synchronization

⚠️ **Be careful when editing** - this controls navigation logic

## 🔌 How It's Integrated

All these files are loaded in `retail/hooks.py`:

```python
app_include_css = [
    "/assets/retail/css/retail_icons.css",
]

app_include_js = [
    "https://cdn.jsdelivr.net/npm/lucide@latest",  # Lucide CDN
    "/assets/retail/js/retail_navigation.js",
    "/assets/retail/js/retail_icons.js",
]
```

## 🚀 Available Icon Names

Lucide has 400+ icons. Common ones used:

**Shopping:**
- `shopping-cart`, `shopping-bag`, `receipt`, `invoice`

**Organization:**
- `users`, `building-2`, `home`, `warehouse`

**Items:**
- `box`, `grid`, `tag`, `package`

**Finance:**
- `dollar-sign`, `credit-card`, `percent`, `calculator`

**Actions:**
- `truck`, `check-square`, `undo-2`, `bookmark`

See full list: **https://lucide.dev/**

## 📝 Future Customizations

To add new CSS or JS files in the future:

1. Create the file in `retail/public/css/` or `retail/public/js/`
2. Add it to `hooks.py` in the `app_include_css` or `app_include_js` list
3. Add a comment in this README explaining what it does

**Example:**
```python
app_include_css = [
    "/assets/retail/css/retail_icons.css",
    "/assets/retail/css/retail_custom.css",  ← New custom file
]
```

## 🔍 How to Find & Edit

1. **Want to change icon colors?** → Edit `retail/public/css/retail_icons.css`
2. **Want to change which icon shows?** → Edit `retail/public/js/retail_icons.js`
3. **Want to change menu behavior?** → Edit `retail/public/js/retail_navigation.js`
4. **Want to add new styling?** → Create new file in `retail/public/css/`

## ✅ Checklist for Future Updates

When making changes:
- [ ] Edit the relevant file in `retail/public/`
- [ ] Test in your local instance
- [ ] Run `bench build` to compile assets
- [ ] Commit changes with clear message
- [ ] Push to GitHub
- [ ] Update this README if adding new files

## 🐛 Troubleshooting

**Icons not showing?**
- Check browser console for errors
- Make sure `bench build` was run
- Clear browser cache (Ctrl+F5)

**Colors not changing?**
- Verify CSS class name matches in `retail_icons.js`
- Check if there's a conflicting CSS rule
- Use browser DevTools to inspect the element

**Need to roll back?**
- Check git history: `git log --oneline retail/public/`
- Revert: `git checkout <commit-hash> retail/public/`

---

**Last Updated:** 2026-06-05  
**Maintained By:** Your Team
