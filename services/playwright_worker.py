import os
import json
import base64
import time
import logging
import asyncio
import sys
from playwright.sync_api import sync_playwright
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from jinja2 import Environment, FileSystemLoader, select_autoescape
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(Exception)
)
def generate_with_gemini(client, model_id, prompt):
    return client.models.generate_content(
        model=model_id,
        contents=prompt
    )

def run_generate_asset_sync(req_dict):
    """Standalone function to run Playwright in a separate process."""
    try:
        # Initialize with Vertex AI
        client = genai.Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location="global"
        )
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            
            # 1. Scrape & Find Contact
            # Use 'domcontentloaded' first so we can start clearing popups immediately
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    page.goto(req_dict['website_url'], timeout=60000, wait_until="domcontentloaded")
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(2)
            
            # Aggressive Popup / Banner / Chat Widget Killer (Run early)
            def kill_popups():
                page.evaluate("""
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
                        '[id*="zsiq"]', /* Zoho Desk */
                        '[class*="tawk"]', /* Tawk.to */
                        'fc-widget' /* Freshchat */
                    ];
                    document.querySelectorAll(selectors.join(', ')).forEach(e => {
                        // Protect main content wrappers from aggressive matches (e.g., Drupal's dialog-off-canvas-main-canvas)
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
                    
                    // Aggressive sweep for fixed/sticky bottom elements that look like popups
                    document.querySelectorAll('*').forEach(e => {
                        const style = window.getComputedStyle(e);
                        if (style.position === 'fixed' || style.position === 'sticky') {
                            const rect = e.getBoundingClientRect();
                            // Don't hide large layout containers (e.g., if the whole app is fixed)
                            if (rect.height > window.innerHeight * 0.5 || rect.width > window.innerWidth * 0.8) {
                                return;
                            }
                            
                            // Target bottom popups to avoid hiding top navigation headers
                            const bottom = parseInt(style.bottom);
                            if (bottom >= 0 && bottom < 300) {
                                 try { 
                                     e.style.setProperty('display', 'none', 'important');
                                     e.style.setProperty('visibility', 'hidden', 'important');
                                     e.style.setProperty('opacity', '0', 'important');
                                 } catch(err){}
                            }
                        }
                    });
                """)
            
            kill_popups()
            
            # Now wait for things to settle a bit, but only up to 3 seconds more if idle
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except:
                pass # Continue even if network not fully idle
            
            # Re-kill popups that might have appeared during network activity
            kill_popups()
            
            # Extract Brand Colors
            brand_colors = page.evaluate("""
                () => {
                    const colors = new Set();
                    const getHex = (rgb) => {
                        if (!rgb || rgb === 'transparent' || rgb === 'rgba(0, 0, 0, 0)') return null;
                        const m = rgb.match(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/);
                        if (m) return "#" + ("0" + parseInt(m[1]).toString(16)).slice(-2) + ("0" + parseInt(m[2]).toString(16)).slice(-2) + ("0" + parseInt(m[3]).toString(16)).slice(-2);
                        const ma = rgb.match(/^rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)$/);
                        if (ma && parseFloat(ma[4]) > 0.5) return "#" + ("0" + parseInt(ma[1]).toString(16)).slice(-2) + ("0" + parseInt(ma[2]).toString(16)).slice(-2) + ("0" + parseInt(ma[3]).toString(16)).slice(-2);
                        return null;
                    };

                    // 1. Root variables
                    const root = getComputedStyle(document.documentElement);
                    for (let i = 0; i < root.length; i++) {
                        const prop = root[i];
                        if (prop.includes('primary') || prop.includes('brand') || prop.includes('accent') || prop.includes('theme')) {
                            const val = root.getPropertyValue(prop).trim();
                            const hex = getHex(val) || (val.startsWith('#') ? val : null);
                            if (hex && /^#[0-9a-f]{6}$/i.test(hex)) colors.add(hex.toLowerCase());
                        }
                    }

                    // 2. Common Elements
                    const selectors = ['header', 'nav', 'button', 'h1', '.btn-primary', '.active'];
                    selectors.forEach(s => {
                        document.querySelectorAll(s).forEach(el => {
                            const style = getComputedStyle(el);
                            [style.backgroundColor, style.color].forEach(c => {
                                const hex = getHex(c);
                                if (hex && /^#[0-9a-f]{6}$/i.test(hex)) {
                                    // Avoid pure black/white unless necessary
                                    if (hex !== '#ffffff' && hex !== '#000000') colors.add(hex.toLowerCase());
                                }
                            });
                        });
                    });

                    return Array.from(colors).slice(0, 8);
                }
            """)
            
            body_text = page.evaluate("document.body.innerText")
            links = page.evaluate("""
                () => Array.from(document.querySelectorAll('a')).map(a => ({ text: a.innerText, href: a.href }))
            """)
            
            # 2. LLM Generation
            template_type = req_dict.get('template_type', 'template')
            include_context = req_dict.get('include_context', True)
            
            context_text = f"Read this firm's website text carefully:\n{body_text[:10000]}\n" if include_context else ""
            
            if template_type == 'prompt':
                email_instruction = f"A highly personalized outreach email based on this specific AI prompt: \"{req_dict['email_template']}\"."
                if include_context:
                    email_instruction += " Use the website context provided above to make it extremely relevant."
            else:
                email_instruction = f"A highly personalized outreach email based on template: \"{req_dict['email_template']}\". Replace [Company Name] and [Practice Area] with real data."

            prompt = f"""
            {context_text}
            
            Website Brand Colors found via CSS: {json.dumps(brand_colors)}

            You are generating a realistic, human-like chat preview for an AI chatbot on this website.
            We want to show a single "Full Conversion Cycle".
            
            Return a strict JSON object with these fields:
            'q1': (MAX 60 CHARS) A natural, conversational question a visitor might ask (e.g. "Do you handle [Service]?").
            'a1': (MAX 200 CHARS) A warm, professional, and specific response from the AI that builds trust.
            'lead_gen': (MAX 120 CHARS) A seamless follow-up asking for their phone number or email to connect them with a specialist.
            'primary_color_hex': Pick the best brand color from the list provided or infer it if the list is empty.
            'contact_url': The best guess for their contact page URL from these links: {json.dumps(links[:50])}.
            'customized_email': {email_instruction}
            
            IMPORTANT: Stricly adhere to the character limits for q1, a1, and lead_gen to ensure they fit the UI.
            Do not use generic placeholders. Use real service names and firm details.
            Output ONLY JSON.
            """
            
            # Use gemini-3.1-pro-preview for smarter message generation
            # It will automatically retry on 503s due to the @retry decorator
            response = generate_with_gemini(client, 'gemini-3.1-pro-preview', prompt)
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            
            gemini_data = json.loads(response_text)
            
            # 3. Handle Screenshots
            os.makedirs(req_dict['save_directory'], exist_ok=True)
            sanitized_name = "".join(x for x in req_dict['company_name'] if x.isalnum()).lower()
            screenshot_filename = f"{sanitized_name}.png"
            screenshot_path = os.path.join(req_dict['save_directory'], screenshot_filename)
            
            bg_path = os.path.join(req_dict['save_directory'], f"bg_{screenshot_filename}")
            page.screenshot(path=bg_path)
            
            with open(bg_path, "rb") as image_file:
                encoded_bg = base64.b64encode(image_file.read()).decode("utf-8")
                
            browser.close()
            return {
                "status": "success",
                "gemini_data": gemini_data,
                "encoded_bg": encoded_bg,
                "screenshot_filename": screenshot_filename,
                "screenshot_path": screenshot_path,
                "bg_path": bg_path,
                "company_name": req_dict.get('company_name'),
                "brand_color": req_dict.get('brand_color')
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def run_composite_screenshot_sync(req_dict, gemini_data, encoded_bg):
    """Second pass to take the composite screenshot once preview data is set."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})

            # Use Jinja2 to render the HTML content directly
            env = Environment(
                loader=FileSystemLoader('templates'),
                autoescape=select_autoescape(['html', 'xml'])
            )
            
            template = env.get_template('preview.html')

            primary_color = req_dict.get("brand_color")
            if not primary_color:
                primary_color = gemini_data.get("primary_color_hex", "#805ad5")

            # Ensure primary color has a '#' prefix
            if primary_color and not primary_color.startswith('#'):
                primary_color = '#' + primary_color

            bot_bg = f"rgba({int(primary_color[1:3], 16)}, {int(primary_color[3:5], 16)}, {int(primary_color[5:7], 16)}, 0.15)"
            bot_text = "#1f2937"
            user_bg = primary_color
            user_text = "#ffffff"
            icon_bg = primary_color
            
            bubbles_template = env.get_template("bubbles.html")
            
            def user_bubble(text):
                return bubbles_template.module.user_bubble(text, user_bg, user_text)

            def bot_bubble(text):
                return bubbles_template.module.bot_bubble(text, icon_bg=icon_bg, primary_color=primary_color)

            def bot_form_bubble(text):
                return bubbles_template.module.bot_form_bubble(text, bot_bg, bot_text, icon_bg, primary_color)
                
            messages = [
                user_bubble(gemini_data.get('q1', 'How can we help?')),
                bot_bubble(gemini_data.get('a1', 'Loading...')),
                bot_form_bubble(gemini_data.get('lead_gen', 'Please provide your details so we can assist you better.'))
            ]
    
            html_content_rendered = "".join(messages)

            html_content = template.render(
                bg_color=primary_color,
                bot_name=req_dict.get("company_name", "AI Assistant"),
                messages_html=html_content_rendered
            )
            
            page.set_content(html_content)
            page.add_style_tag(content=".chatbot-container .message-bubble div { text-align: left !important; }")
            
            bg_data_uri = f"data:image/png;base64,{encoded_bg}"
            
            # Apply the background and wait for it to load
            page.evaluate(f"""
                async (bg_data_uri) => {{
                    const bg = document.getElementById('bg-image-container');
                    if (bg) {{
                        return new Promise((resolve, reject) => {{
                            const img = new Image();
                            img.onload = () => {{
                                bg.style.backgroundImage = `url("${{bg_data_uri}}")`;
                                bg.style.backgroundSize = 'cover';
                                bg.style.backgroundPosition = 'top left';
                                resolve();
                            }};
                            img.onerror = reject;
                            img.src = bg_data_uri;
                        }});
                    }}
                }}
            """, bg_data_uri)
            
            # Wait for content to settle and bubbles to be visible
            try:
                page.wait_for_selector(".message-bubble", state="visible", timeout=3000)
            except:
                pass # Continue even if selector fails, maybe it's just slow
            
            page.screenshot(path=req_dict['screenshot_path'])
            browser.close()
            return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def run_fill_form_sync(req_dict):
    """Standalone process for form filling."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            # Wait until network is idle or at least DOM is loaded
            try:
                page.goto(req_dict['contact_url'], timeout=60000, wait_until="networkidle")
            except:
                page.wait_for_load_state("domcontentloaded")
            
            page.evaluate(f"""
                () => {{
                    const nameFields = document.querySelectorAll('input[name*="name" i], input[id*="name" i], input[placeholder*="name" i]');
                    if (nameFields.length > 0) nameFields[0].value = "Osman";
                    
                    const emailFields = document.querySelectorAll('input[type="email"], input[name*="email" i], input[id*="email" i]');
                    if (emailFields.length > 0) emailFields[0].value = "osman.h.dev@gmail.com";
                    
                    const textareas = document.querySelectorAll('textarea');
                    if (textareas.length > 0) {{
                        textareas[0].value = `{req_dict['email_text']}`;
                        textareas[0].scrollIntoView();
                    }}
                }}
            """)
            
            print("Form pre-filled. Please review and click submit manually.")
            try:
                # In headless=False, pause() keeps the browser open for the user
                page.pause()
            except:
                # If pause fails, wait for a long time or until browser is closed
                # But let's use a loop to check if browser is still open
                while True:
                    if not browser.is_connected():
                        break
                    time.sleep(1)
                
            browser.close()
            return {"status": "completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
