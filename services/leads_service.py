import httpx
from fastapi import HTTPException

async def get_source_leads(query: str, limit: int, google_maps_api_key: str, page_token: str = None):
    if not google_maps_api_key:
        raise HTTPException(status_code=500, detail="Missing GOOGLE_MAPS_API_KEY")

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": google_maps_api_key,
        "X-Goog-FieldMask": "places.displayName,places.websiteUri,nextPageToken"
    }
    payload = {
        "textQuery": query,
        "maxResultCount": min(limit, 20)
    }

    if page_token:
        payload["pageToken"] = page_token

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        data = resp.json()
        places = data.get("places", [])
        next_token = data.get("nextPageToken")

        results = []
        for p in places:
            name = p.get("displayName", {}).get("text")
            website = p.get("websiteUri")
            if website:
                results.append({"company_name": name, "website_url": website})

        return {
            "leads": results,
            "next_page_token": next_token
        }
