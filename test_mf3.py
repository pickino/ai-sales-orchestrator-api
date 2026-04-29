import os
from playwright.sync_api import sync_playwright
import time
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    page.goto('https://www.mindflares.com/', wait_until='networkidle')
    
    page.evaluate('''
                    const selectors = [
                        '[id*="cookie"]', '[class*="cookie"]',
                        '[id*="banner"]', '[class*="banner"]',
                        '[id*="popup"]', '[class*="popup"]',
                        '[id*="modal"]', '[class*="modal"]',
                        '[id*="dialog"]', '[class*="dialog"]',
                        '[id*="consent"]', '[class*="consent"]',
                        '[id*="cky-"]', '[class*="cky-"]',
                        'iframe[src*="chat"]', 'iframe[src*="intercom"]',
                        '#intercom-container', '#hubspot-messages-iframe-container',
                        '#drift-widget', '.drift-widget-container',
                        '[class*="chatbot"]', '[id*="chatbot"]',
                        '[id*="zsiq"]',
                        '[class*="tawk"]',
                        'fc-widget'
                    ];
                    document.querySelectorAll(selectors.join(', ')).forEach(e => {
                        // Protect main content wrappers from aggressive matches
                        const id = e.id.toLowerCase();
                        const cls = e.className.toString().toLowerCase();
                        if (e.tagName === 'BODY' || e.tagName === 'MAIN' || e.tagName === 'HTML' ||
                            id.includes('main') || cls.includes('main') || 
                            id.includes('page') || cls.includes('page') || 
                            id.includes('wrapper') || cls.includes('wrapper')) {
                            return; // skip
                        }
                        
                        try { 
                            e.style.setProperty('display', 'none', 'important');
                            e.style.setProperty('visibility', 'hidden', 'important');
                            e.style.setProperty('opacity', '0', 'important');
                        } catch(err){}
                    });
    ''')
    time.sleep(3)
    page.screenshot(path='test_mindflares_fixed.png')
    browser.close()
    
    print(os.path.getsize('test_mindflares_fixed.png'))
