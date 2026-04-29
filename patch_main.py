import sys
import re

path = r"C:\Users\K\outreach-fastapi\main.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# Fix 1: Change iconBackgroundColor from #ffffff to the bg_color (so the white icon shows up!)
text = text.replace(
    '"iconBackgroundColor": "#ffffff"',
    '"iconBackgroundColor": bg_color' # In the python code context
)
# Wait, in the HTML template string, bg_color isn't defined directly there, let's look at how preview_widget creates it:
# config_dict = {
#   ...
#   "themeConfigData": {
#       "header": {"backgroundColor": bg_color, "textColor": "#ffffff", "iconBackgroundColor": "#ffffff"},

text = text.replace(
    '"iconBackgroundColor": "#ffffff"',
    '"iconBackgroundColor": bg_color'
)

# Fix 2: Improve the Playwright click logic in generate_asset
old_click_logic = """            # Click the chatbot to open it
            await page.evaluate(\"\"\"
                try {
                    const btn = document.querySelector('.w-14.h-14.rounded-full');
                    if (btn) btn.click();
                } catch(e) {
                    console.error("Failed to click chatbot button:", e);
                }
            \"\"\")"""

new_click_logic = """            # Wait for the chatbot button and click it reliably
            btn_selector = ".w-14.h-14.rounded-full"
            try:
                await page.wait_for_selector(btn_selector, state="visible", timeout=10000)
                await page.click(btn_selector)
            except Exception as e:
                logger.error(f"Failed to click chatbot: {e}")
                # Fallback evaluate click
                await page.evaluate("document.querySelector('.w-14.h-14.rounded-full')?.click();")"""

if old_click_logic in text:
    text = text.replace(old_click_logic, new_click_logic)
else:
    print("Could not find the old click logic to replace!")

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

print("Patched main.py")