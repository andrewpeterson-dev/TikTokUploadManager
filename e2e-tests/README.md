# TikTok Upload Manager - End-to-End Testing Suite

## Overview
Playwright-based automated testing for the TikTok Upload Manager application.

## Prerequisites
- Node.js v25+ installed
- Python 3.9+ installed
- TikTok Upload Manager app running on `http://localhost:8000`

## Installation
All dependencies are already installed. If you need to reinstall:

```bash
npm install
npx playwright install
```

## Running Tests

### Run all tests (headless mode)
```bash
npm test
```

### Run tests with browser UI visible
```bash
npm run test:headed
```

### Run tests in debug mode (step-by-step)
```bash
npm run test:debug
```

### View test report
```bash
npm run test:report
```

### Run specific test file
```bash
npx playwright test e2e.spec.js
```

### Run specific test by name
```bash
npx playwright test -g "Full TikTok Upload Flow"
```

### Run on specific browser
```bash
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

## Test Coverage

### 1. Full TikTok Upload Flow Test
Complete end-to-end workflow:
- App loads
- Video generation
- Video library display
- TikTok OAuth connection
- Video upload
- Status tracking
- Success verification

### 2. Video Library Test
- Loads video library
- Displays video cards
- Verifies UI elements

### 3. Video Generation Test
- Creates new video
- Verifies generation completion
- Checks video appears in library

### 4. TikTok OAuth Test
- Initiates OAuth flow
- Redirects to TikTok
- Handles callback

### 5. Upload Status Test
- Tracks upload progress
- Monitors status transitions
- Verifies completion

### 6. Error Handling Test
- Simulates upload failures
- Verifies error messages
- Tests recovery

### 7. UI Responsiveness Test
- Desktop view (1920x1080)
- Tablet view (768x1024)
- Mobile view (375x667)

### 8. Concurrent Uploads Test
- Multiple video selection
- Batch upload
- Parallel upload tracking

## Configuration
All configuration is in `playwright.config.js`:
- Base URL: `http://localhost:8000`
- Auto-starts dev server if not running
- Captures screenshots on failure
- Records video on failure
- Generates HTML report

## Troubleshooting

### Tests fail with "page.goto: net::ERR_CONNECTION_REFUSED"
- Make sure the TikTok Upload Manager app is running
- Verify it's accessible at `http://localhost:8000`
- Check the webServer configuration in `playwright.config.js`

### OAuth tests timeout
- OAuth flows may need mocking for faster testing
- Adjust timeout values in test file
- Consider using Playwright's request interception

### Video generation tests fail
- Increase waitForTimeout duration
- Check if backend processing is complete
- Verify video card selectors match your HTML

## CI/CD Integration
Tests are configured for CI environments:
- Retries: 2 (in CI)
- Workers: 1 (in CI)
- Screenshots and videos saved on failure

## Next Steps
- Add API mocking for faster tests
- Implement visual regression testing
- Add performance benchmarking
- Expand test coverage to edge cases
