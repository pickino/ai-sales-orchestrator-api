import asyncio
import sys
import os
import json
import logging
import time
import multiprocessing as mp
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape
from concurrent.futures import ProcessPoolExecutor
from google import genai
from google.genai import types

# Local Imports
from models import SourceLeadsRequest, GenerateAssetRequest, FillFormRequest, ChatRequest
from services.leads_service import get_source_leads
from services.playwright_worker import (
    run_generate_asset_sync,
    run_composite_screenshot_sync,
    run_fill_form_sync
)

def init_worker():
    """Sets the event loop policy for the worker process."""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Fix for Windows asyncio loop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()

# Logging
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)


app = FastAPI(title="Guerrilla Outreach Worker")
templates = Jinja2Templates(directory="templates")

# Create a ProcessPoolExecutor with the worker initializer
executor = ProcessPoolExecutor(max_workers=mp.cpu_count(), initializer=init_worker)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Note: google-genai client will be initialized in the worker process.

@app.get("/preview", response_class=HTMLResponse)
async def preview_widget(request: Request):
    return templates.TemplateResponse(
        "preview.html",
        {
            "request": request,
            "bg_color": "#805ad5",
            "bot_name": "AI Assistant",
            "messages_html": ""
        }
    )

@app.post("/api/source-leads")
async def source_leads(req: SourceLeadsRequest):
    start_time = time.time()
    logger.info(f"Received /api/source-leads request with query: '{req.query}'")
    result = await get_source_leads(req.query, req.limit, GOOGLE_MAPS_API_KEY, req.page_token)
    total_time = time.time() - start_time
    logger.info(f"Finished /api/source-leads request in {total_time:.2f} seconds.")
    return result

@app.post("/api/generate-asset")
async def generate_asset(req: GenerateAssetRequest):
    start_time = time.time()
    logger.info(f"Received /api/generate-asset request for {req.company_name}")

    loop = asyncio.get_running_loop()
    req_dict = req.dict()
    req_dict['company_name'] = req.company_name

    try:
        logger.info("Starting Playwright process for asset generation...")
        step_start_time = time.time()
        result = await loop.run_in_executor(
            executor, run_generate_asset_sync, req_dict
        )
        logger.info(f"Playwright process finished in {time.time() - step_start_time:.2f} seconds.")

    except Exception as e:
        logger.error(f"Playwright process failed: {e}")
        raise HTTPException(status_code=500, detail=f"Playwright process failed: {e}")

    if result.get("status") == "error":
        logger.error(f"Asset generation failed with error: {result.get('message')}")
        raise HTTPException(status_code=500, detail=result.get("message"))

    gemini_data = result["gemini_data"]
    logger.info("Successfully generated Gemini data.")

    try:
        logger.info("Starting composite screenshot process...")
        step_start_time = time.time()
        final_result = await loop.run_in_executor(
            executor, run_composite_screenshot_sync, result, gemini_data, result["encoded_bg"]
        )
        logger.info(f"Composite screenshot process finished in {time.time() - step_start_time:.2f} seconds.")
    except Exception as e:
        logger.error(f"Composite screenshot process failed: {e}")
        raise HTTPException(status_code=500, detail=f"Composite screenshot process failed: {e}")

    try:
        os.remove(result["bg_path"])
        logger.info(f"Removed temporary background file: {result['bg_path']}")
    except Exception as e:
        logger.warning(f"Could not remove temporary file {result.get('bg_path', 'N/A')}: {e}")


    if final_result.get("status") == "error":
         logger.error(f"Composite screenshot failed with error: {final_result.get('message')}")
         raise HTTPException(status_code=500, detail=final_result.get("message"))

    total_time = time.time() - start_time
    logger.info(f"Successfully processed /api/generate-asset request for {req.company_name} in {total_time:.2f} seconds.")

    return {
        "screenshot_filename": result["screenshot_filename"],
        "email_text": gemini_data.get("customized_email", ""),
        "contact_url": gemini_data.get("contact_url", req.website_url),
        "brand_color": req.brand_color if req.brand_color else gemini_data.get("primary_color_hex", "#805ad5")
    }

@app.post("/api/fill-form")
async def fill_form(req: FillFormRequest):
    start_time = time.time()
    logger.info(f"Received /api/fill-form request for URL: {req.url}")
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            executor, run_fill_form_sync, req.dict()
        )
        total_time = time.time() - start_time
        logger.info(f"Finished /api/fill-form request in {total_time:.2f} seconds.")
        return result
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"Form fill process for {req.url} failed in {total_time:.2f} seconds: {e}")
        return {"status": "error", "message": f"Form fill process failed: {e}"}

@app.get("/test-chat-preview", response_class=HTMLResponse)
async def test_chat_preview(request: Request):
    # This endpoint uses Jinja2 directly to bypass the full Playwright process
    env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=select_autoescape(['html', 'xml'])
    )

    # Hardcoded data for fast preview
    primary_color = "#2d3748" # A neutral dark color
    user_bg = primary_color
    user_text = "#ffffff"
    icon_bg = primary_color
    
    # Render bubbles
    bubbles_template = env.get_template("bubbles.html")
    q1 = "\n\nCan you help me with a temporary work visa?"
    a1 = "Absolutely! With 30+ years of experience, we specialize in temporary work visas and employment residency."
    lead_gen = "To help you better, could you share your name and email?"

    messages_html = "".join([
        bubbles_template.module.user_bubble(q1, user_bg, user_text),
        bubbles_template.module.bot_bubble(a1, "", "", icon_bg, primary_color),
        bubbles_template.module.bot_form_bubble(lead_gen, "", "", icon_bg, primary_color)
    ])

    # Render main preview template
    template = env.get_template('preview.html')
    html_content = template.render(
        request=request,
        bg_color=primary_color,
        bot_name="Test Widget (Live Edit)",
        messages_html=messages_html
    )
    return HTMLResponse(content=html_content)


@app.post("/api/chat")
@app.post("/process-message")
async def chat_endpoint(req: ChatRequest):
    logger.info(f"Received chat request: {req.message[:50]}...")
    
    if req.is_warm_up:
        logger.info("Warm-up request received. Returning success.")
        return {"status": "warmed_up"}

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    contents = []
    for h in req.history:
        role = "user" if h["sender"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=h["text"])]))
    
    # Add the current message
    contents.append(types.Content(role="user", parts=[types.Part(text=req.message)]))

    async def generate():
        try:
            # We use the async client for streaming to avoid blocking the event loop
            async for chunk in client.aio.models.generate_content_stream(
                model='gemini-2.0-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=req.instructions,
                    temperature=0.7,
                    max_output_tokens=1000,
                )
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Error during streaming: {e}")
            yield f"Error: {str(e)}"

    return StreamingResponse(generate(), media_type="text/plain")


@app.get("/test")
async def test_endpoint():
    return {"status": "ok"}

if __name__ == "__main__":
    mp.freeze_support()
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
