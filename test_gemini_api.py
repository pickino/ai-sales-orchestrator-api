import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

def test_api():
    api_key = os.getenv("GEMINI_API_KEY")
    print(f"Testing with API Key: {api_key[:5]}...{api_key[-5:]}")
    
    # If the key starts with AQ., it might be a Vertex AI key
    is_vertex = api_key.startswith("AQ.")
    
    try:
        # Standard initialization (even for AQ keys, google-genai handles them if they are for AI Studio/Vertex pass-through)
        client = genai.Client(api_key=api_key)

        # Let's try to just generate first as listing might require more permissions
        print("\nAttempting generation with gemini-3-flash-preview...")
        response = client.models.generate_content(
            model='gemini-3-flash-preview',
            contents='Hello, are you there?'
        )
        print(f"Response: {response.text}")
        
    except Exception as e:
        print(f"Error: {e}")
        
        # Second attempt with vertexai if first failed with auth error
        if "401" in str(e) or "Unauthorized" in str(e):
            print("\nRetrying with vertexai=True (and without manual api_key, assuming environment variables might be used)...")
            try:
                # If API key is provided, vertexai=True might still be needed in some contexts
                # But the error said they are mutually exclusive. 
                # This usually means if vertexai=True, you use ADCs.
                # However, if it's an AQ. key, it might NOT be a Vertex AI key in the traditional sense.
                pass
            except:
                pass
if __name__ == "__main__":
    test_api()
