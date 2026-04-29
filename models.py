from pydantic import BaseModel
from typing import Optional, List, Dict

class SourceLeadsRequest(BaseModel):
    query: str
    limit: int = 20
    page_token: Optional[str] = None

class GenerateAssetRequest(BaseModel):
    website_url: str
    company_name: str
    save_directory: str
    email_template: str
    template_type: Optional[str] = "template"
    include_context: Optional[bool] = True
    brand_color: Optional[str] = None

class FillFormRequest(BaseModel):
    contact_url: str
    email_text: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []
    unique_name: Optional[str] = None
    instructions: Optional[str] = None
    is_warm_up: bool = False
