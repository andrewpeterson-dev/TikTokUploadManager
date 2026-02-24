# 🚀 Quick Start Guide

## ✅ Status: SETUP COMPLETE

All Playwright dependencies installed and configured!

## 🎯 Run Your First Test (3 Commands)

### 1. Navigate to test directory
```bash
cd /Users/andrewpeterson/TikTokUploadManager/e2e-tests
```

### 2. Run tests (headed mode - see browser)
```bash
npm run test:headed
```

### 3. View results
```bash
npm run test:report
```

## 📊 What's Installed

✅ **@playwright/test** - Testing framework
✅ **Chromium** - Chrome browser for testing
✅ **Firefox** - Firefox browser for testing
✅ **WebKit** - Safari browser for testing

## 🧪 5 Tests Ready to Run

1. **Full TikTok Upload Flow Test** - Complete end-to-end workflow
2. **Video Generation Test** - Isolated video creation
3. **TikTok OAuth Connection Test** - OAuth redirect validation
4. **Video Library Display Test** - UI rendering verification
5. **Upload Button State Test** - Button state management

## ⚡ Quick Commands

| Command | What It Does |
|---------|-------------|
| `npm test` | Run all tests (headless) |
| `npm run test:headed` | Run tests with visible browser |
| `npm run test:debug` | Debug with Playwright Inspector |
| `npm run test:report` | Open HTML test report |

## 🔍 Before Running Tests

**Make sure your TikTok Upload Manager app is running on port 8000:**

```bash
cd /Users/andrewpeterson/TikTokUploadManager
python3 -m http.server 8000
```

Or if you have a custom start script, run that first.

## 📁 Files Created

```
e2e-tests/
├── e2e.spec.js           ✅ 5 test suites
├── playwright.config.js   ✅ Configuration
├── package.json           ✅ Dependencies + scripts
├── README.md              ✅ Full documentation
└── QUICK_START.md         ✅ This file
```

## 💡 Next Steps

1. **Start your app** (if not already running)
2. **Run**: `npm run test:headed`
3. **Watch tests execute** in the browser
4. **Check results** in the terminal + HTML report

## 🆘 Need Help?

- **Tests failing?** Check if app is running on port 8000
- **OAuth issues?** Tests expect real TikTok credentials (or mock them)
- **Timeouts?** Increase timeout values in `playwright.config.js`
- **Full docs?** See `README.md` for comprehensive guide

---

**Ready to go!** 🎉
Run `npm run test:headed` to start testing.
