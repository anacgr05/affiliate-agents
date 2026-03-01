import os
import logging
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.image_gen import generate_hero_image

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env vars
load_dotenv()

def test_gen():
    print("Testing Image Generation...")
    api_key = os.getenv("OPENROUTER_API_KEY")
    print(f"API Key present: {bool(api_key)}")
    
    prompt = "An illustrative, stylized image of a high-performance computer processor glowing with energy, surrounded by gaming elements like FPS counters and performance metrics flowing around it. Modern, tech-forward aesthetic with vibrant colors suggesting power and speed. Not photorealistic, but believable and engaging."
    
    url = generate_hero_image(prompt)
    print(f"Result URL: {url}")

if __name__ == "__main__":
    test_gen()
