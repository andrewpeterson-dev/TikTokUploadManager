const { test, expect } = require('@playwright/test');

test('Full TikTok Upload Flow Test', async ({ page }) => {

  // Launch local app URL
  await page.goto('http://localhost:8000');

  // Ensure app loads
  await expect(page.locator('text=Video Library')).toBeVisible();

  // Click generate video
  await page.click('text=Generate Video');

  // Wait for video generation (adjust timeout as needed)
  await page.waitForTimeout(3000);

  // Verify video appears in library
  const videoCard = page.locator('.video-card').first();
  await expect(videoCard).toBeVisible();

  // Click connect TikTok (OAuth flow)
  await page.click('text=Connect TikTok');

  // Wait for redirect to TikTok auth page
  await page.waitForURL(/.*tiktok.*/);

  // Simulate OAuth callback redirect (mock or real)
  await page.goto('http://localhost:8000/callback/?code=fake_auth_code');

  // Verify connected state
  await expect(page.locator('text=Connected')).toBeVisible();

  // Post video to TikTok
  await page.click('text=Post Video');

  // Wait for upload status update
  await expect(page.locator('text=Uploading')).toBeVisible();

  // Wait for success message
  await expect(page.locator('text=Posted Successfully')).toBeVisible({ timeout: 30000 });

  console.log('✅ Full upload flow test passed!');
});

test('Video Library - Load and Display Videos', async ({ page }) => {
  await page.goto('http://localhost:8000');

  // Wait for library to load
  await expect(page.locator('text=Video Library')).toBeVisible();

  // Check that at least one video card is present
  const videoCards = page.locator('.video-card');
  await expect(videoCards.first()).toBeVisible();

  console.log('✅ Video library loads correctly');
});

test('Video Generation - Create New Video', async ({ page }) => {
  await page.goto('http://localhost:8000');

  // Click generate button
  await page.click('text=Generate Video');

  // Wait for generation to complete
  await page.waitForTimeout(5000);

  // Verify new video appears
  const newVideo = page.locator('.video-card').first();
  await expect(newVideo).toBeVisible();

  console.log('✅ Video generation successful');
});

test('TikTok OAuth - Connection Flow', async ({ page }) => {
  await page.goto('http://localhost:8000');

  // Click connect button
  await page.click('text=Connect TikTok');

  // Should redirect to TikTok auth
  await page.waitForURL(/.*tiktok.*/, { timeout: 10000 });

  console.log('✅ OAuth redirect working');
});

test('Upload Status - Track Progress', async ({ page }) => {
  await page.goto('http://localhost:8000');

  // Assume video already exists and is selected
  await page.click('text=Post Video');

  // Check for status transitions
  await expect(page.locator('text=Uploading')).toBeVisible();

  // Wait for completion (may need to mock for faster testing)
  await expect(page.locator('text=Posted Successfully')).toBeVisible({ timeout: 30000 });

  console.log('✅ Upload status tracking works');
});

test('Error Handling - Failed Upload', async ({ page }) => {
  await page.goto('http://localhost:8000');

  // Simulate failed upload scenario (may require mocking API)
  await page.click('text=Post Video');

  // Mock network failure or error response
  await page.route('**/upload', route => route.abort());

  // Verify error message appears
  await expect(page.locator('text=Upload Failed')).toBeVisible({ timeout: 10000 });

  console.log('✅ Error handling verified');
});

test('UI Responsiveness - Multiple Screen Sizes', async ({ page }) => {
  // Test desktop view
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto('http://localhost:8000');
  await expect(page.locator('text=Video Library')).toBeVisible();

  // Test tablet view
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto('http://localhost:8000');
  await expect(page.locator('text=Video Library')).toBeVisible();

  // Test mobile view
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto('http://localhost:8000');
  await expect(page.locator('text=Video Library')).toBeVisible();

  console.log('✅ Responsive design works across screen sizes');
});

test('Concurrent Uploads - Multiple Videos', async ({ page }) => {
  await page.goto('http://localhost:8000');

  // Select multiple videos
  await page.click('.video-card:nth-child(1) .select-checkbox');
  await page.click('.video-card:nth-child(2) .select-checkbox');

  // Initiate batch upload
  await page.click('text=Upload Selected');

  // Verify multiple upload progress indicators
  const uploadingIndicators = page.locator('text=Uploading');
  await expect(uploadingIndicators).toHaveCount(2);

  console.log('✅ Concurrent uploads supported');
});
