import asyncio
from pyppeteer import launch

async def take_screenshots():
    browser = await launch(
        executablePath=r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox']
    )
    
    # ── 1. Retake ui-dashboard.png (1618 x 894) ──────────────────────────────
    page = await browser.newPage()
    await page.setViewport({'width': 1618, 'height': 894, 'deviceScaleFactor': 1})
    await page.goto('http://127.0.0.1:8000', {'waitUntil': 'networkidle0'})
    
    # Inject auth token into localStorage and reload
    await page.evaluate('''() => {
        fetch('/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: 'demo@example.com', password: 'Password123!'})
        }).then(r => r.json()).then(data => {
            localStorage.setItem('token', data.access_token);
            location.reload();
        });
    }''')
    
    # Wait for page to reload and load documents
    await page.waitForNavigation({'waitUntil': 'networkidle0'})
    await page.waitFor(2000)
    
    # Capture dashboard
    dashboard_path = r'C:\Users\Isra\Downloads\internship2\ui-dashboard.png'
    await page.screenshot({'path': dashboard_path})
    print(f"Captured ui-dashboard to {dashboard_path}")
    
    # ── 2. Retake ui-chat.png (1522 x 840) ───────────────────────────────────
    await page.setViewport({'width': 1522, 'height': 840, 'deviceScaleFactor': 1})
    
    # Click on the first document: ocr_invoice_receipt.png
    doc_cards = await page.querySelectorAll('.doc-card')
    if doc_cards:
        await doc_cards[0].click()
        print("Clicked on ocr_invoice_receipt.png doc card")
        await page.waitFor(1500)
        
        # Send first question: "How many new enterprise clients joined?"
        await page.type('#chat-input', 'How many new enterprise clients joined?')
        await page.click('#btn-send')
        print("Sent first prompt, waiting for response...")
        await page.waitFor(5000)
        
        # Send second question: "What is the invoice ID and total amount due?"
        await page.type('#chat-input', 'What is the invoice ID and total amount due?')
        await page.click('#btn-send')
        print("Sent second prompt, waiting for response...")
        await page.waitFor(8000)
        
        chat_path = r'C:\Users\Isra\Downloads\internship2\ui-chat.png'
        await page.screenshot({'path': chat_path})
        print(f"Captured ui-chat to {chat_path}")
        
    await browser.close()

asyncio.get_event_loop().run_until_complete(take_screenshots())
