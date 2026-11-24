export default async function run(page, ui) {
  await ui.click('@e3')
  await page.waitForTimeout(1200)
  await page.screenshot({ path: 'C:/Users/AWD/Desktop/TEST TECHNIQUE/frontend/agent-dashboard.png', fullPage: true })
  return { snapshot: await ui.snapshot({full:true}), body: await page.locator('body').innerText() }
}
