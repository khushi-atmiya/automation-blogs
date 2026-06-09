import requests
import urllib.parse

def debug_ai():
    p_style = "margin-bottom: 20px; font-family: 'Inter', system-ui, -apple-system, sans-serif; font-size: 16px; line-height: 1.8; color: #2d3436; text-align: justify;"
    strong_style = "color: #0984e3;"
    
    prompt = (
        f"Create an extremely detailed, 1500-word professional blog post about 'AI in Technology'. \n\n"
        "STRICT REQUIREMENTS:\n"
        "1. Length: Minimum 1500 words.\n"
        "2. Format: Return a JSON object with 'title' and 'description' (a list of 10-15 long paragraphs).\n"
        f"3. HTML Decoration: Wrap each paragraph string in <p style=\"{p_style}\">...</p>\n"
    )
    
    encoded_prompt = urllib.parse.quote(prompt)
    text_url = f"https://text.pollinations.ai/{encoded_prompt}?model=openai"
    
    print(f"Requesting: {text_url[:100]}...")
    response = requests.get(text_url)
    print("Status Code:", response.status_code)
    print("Response Length:", len(response.text))
    print("Response Start:", response.text[:500])
    print("Response End:", response.text[-500:])

if __name__ == "__main__":
    debug_ai()
