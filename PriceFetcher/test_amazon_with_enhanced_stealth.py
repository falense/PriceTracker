import asyncio
from playwright.async_api import async_playwright
import sys
sys.path.insert(0, 'src')
from stealth import (
    STEALTH_ARGS,
    apply_stealth,
    get_enhanced_context_options,
    simulate_human_behavior,
    wait_for_stable_load
)

async def test_fetch():
    url = "https://www.amazon.com/OXO-Non-Stick-Ceramic-Bakeware-3-Piece/dp/B0F1P5N81H/"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=STEALTH_ARGS)
        context = await browser.new_context(**get_enhanced_context_options("amazon.com"))
        page = await context.new_page()
        await apply_stealth(page)
        
        await page.goto(url, wait_until='load', timeout=60000)
        
        # Simulate human behavior
        await wait_for_stable_load(page, timeout=30000)
        await simulate_human_behavior(page, "amazon.com")
        
        html = await page.content()
        
        # Save HTML for inspection
        with open('amazon_product_page.html', 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✓ Saved {len(html)} bytes to amazon_product_page.html")
        
        # Check for key elements
        print(f"\nKey elements found:")
        print(f"  Contains 'Add to Cart': {'Add to Cart' in html}")
        print(f"  Contains product title span: {'<span id=\"productTitle\"' in html}")
        print(f"  Contains price whole: {'<span class=\"a-price-whole\">' in html}")
        print(f"  Contains price symbol: {'<span class=\"a-price-symbol\">' in html}")
        print(f"  Contains CAPTCHA: {'captcha' in html.lower()}")
        
        await browser.close()

asyncio.run(test_fetch())
