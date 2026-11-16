import asyncio
from pyppeteer import launch

async def capture_chat():
    browser = await launch(
        executablePath=r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox']
    )
    
    page = await browser.newPage()
    await page.setViewport({'width': 1522, 'height': 840, 'deviceScaleFactor': 1})
    await page.goto('http://127.0.0.1:8000', {'waitUntil': 'networkidle0'})
    
    # Inject token and select document
    await page.evaluate('''() => {
        fetch('/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: 'demo_user@itgate.tn', password: 'Password123!'})
        }).then(r => r.json()).then(data => {
            localStorage.setItem('token', data.access_token);
            location.reload();
        });
    }''')
    
    await page.waitForNavigation({'waitUntil': 'networkidle0'})
    await page.waitFor(2000)
    
    # Click the first card
    await page.evaluate('''() => {
        const cards = document.querySelectorAll('.doc-card');
        for (const c of cards) {
            if (c.innerText.includes('ocr_invoice_receipt.png')) {
                c.click();
                break;
            }
        }
    }''')
    await page.waitFor(1500)
    
    # First question
    print("Typing Q1...")
    await page.type('#chat-input', 'How many new enterprise clients joined?')
    await page.click('#chat-send')
    print("Sent Q1, waiting for response...")
    await page.waitFor(6000)
    
    # Second question
    print("Typing Q2...")
    await page.type('#chat-input', 'What is the invoice ID and total amount due?')
    await page.click('#chat-send')
    print("Sent Q2, waiting for response...")
    await page.waitFor(9000)
    
    chat_path = r'C:\Users\Isra\Downloads\internship2\ui-chat.png'
    await page.screenshot({'path': chat_path})
    print(f"Captured ui-chat to {chat_path}")
    
    await browser.close()

asyncio.get_event_loop().run_until_complete(capture_chat())
