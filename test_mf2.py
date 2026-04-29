import os
from playwright.sync_api import sync_playwright
import time
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    page.goto('https://www.mindflares.com/', wait_until='networkidle')
    
    hidden_elements = page.evaluate('''
        () => {
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
            
            const results = [];
            document.querySelectorAll(selectors.join(', ')).forEach(e => {
                results.push({ tag: e.tagName, id: e.id, class: e.className, reason: 'selector' });
            });
            
            document.querySelectorAll('*').forEach(e => {
                        const style = window.getComputedStyle(e);
                        if (style.position === 'fixed' || style.position === 'sticky') {
                            const rect = e.getBoundingClientRect();
                            if (rect.height > window.innerHeight * 0.5 || rect.width > window.innerWidth * 0.8) {
                                return;
                            }
                            
                            const bottom = parseInt(style.bottom);
                            if (bottom >= 0 && bottom < 300) {
                                 results.push({ tag: e.tagName, id: e.id, class: e.className, reason: 'fixed_bottom' });
                            }
                        }
                    });
                    
            return results;
        }
    ''')
    print(hidden_elements)
    browser.close()
