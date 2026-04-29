# Outreach Project - FastAPI Microservice

## Overview
This is the "Muscle" component of the Outreach project. It handles data-intensive and browser-based tasks. It's designed to be a high-performance utility service for the Laravel primary application.

### Key Capabilities
1.  **Lead Sourcing:** Uses Google Maps API (or similar) to find businesses based on location and keywords.
2.  **Asset Generation:**
    -   Uses Playwright to capture high-quality screenshots and extract CSS brand colors from business websites.
    -   Integrates with Google's latest Gemini models (specifically `gemini-3.1-pro-preview`) to analyze website context, generate personalized outreach content, and infer the website's primary brand color for accurate UI generation.
3.  **Automation:**
    -   Uses Playwright to automate filling contact forms on business websites.
    -   Handles complex web navigation and interaction.

### Tech Stack
-   **Framework:** FastAPI
-   **Language:** Python 3.12+
-   **Core Libraries:** Playwright, Pydantic, HTTPX, uvicorn
-   **Deployment:** Runs on `http://127.0.0.1:8001` (local development)

### Directory Structure
-   `main.py`: Entry point and API route definitions.
-   `models.py`: Pydantic models for request/response validation.
-   `services/`: Core business logic (Playwright automation, sourcing, etc.).
-   `storage/`: Temporary storage for generated assets (screenshots, etc.).

---
*Main Project Context:* [C:/Users/K/Herd/outreach/GEMINI.md](C:/Users/K/Herd/outreach/GEMINI.md)
