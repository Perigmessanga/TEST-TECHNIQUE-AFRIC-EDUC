export default async function run(page, ui) {
  await ui.click('@e3')
  await page.waitForTimeout(1500)
  const body=await page.locator('body').innerText()
  await page.screenshot({path:'C:/Users/AWD/Desktop/TEST TECHNIQUE/frontend/agent-dashboard.png',fullPage:true})
  return {body,snapshot:await ui.snapshot({full:true})}
}
