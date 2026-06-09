import requests

def test_pollinations():
    prompt = "Create a professional blog post title and a 300-word blog post about 'The impact of AI on jobs in the UK' in JSON format with 'title' and 'content' fields."
    url = f"https://text.pollinations.ai/{prompt}?model=openai"
    try:
        response = requests.get(url)
        print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_pollinations()
