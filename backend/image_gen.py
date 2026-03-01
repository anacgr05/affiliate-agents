import os
import logging
import requests
import json

logger = logging.getLogger(__name__)

def generate_hero_image(prompt):
    """
    Generates an image using OpenRouter's 'google/gemini-2.5-flash-image' model.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("❌ No OPENROUTER_API_KEY found.")
        return "https://placehold.co/1200x600?text=No+API+Key"

    model = "google/gemini-2.5-flash-image"
    logger.info(f"🎨 Generating Image with {model} for prompt: '{prompt}'")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000", # Required by OpenRouter
        "X-Title": "Affiliate Agents" # Required by OpenRouter
    }

    # Try standard Image Generation Endpoint
    url = "https://openrouter.ai/api/v1/images/generations"
    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                image_url = data["data"][0]["url"]
                logger.info(f"✅ Image generated successfully: {image_url}")
                return image_url
            else:
                logger.warning(f"⚠️ Unexpected response format: {data}")
        else:
            logger.warning(f"⚠️ Image Endpoint failed ({response.status_code}): {response.text}. Trying Chat Endpoint...")
            
            # Fallback: Chat Completion Endpoint (Some models work this way)
            chat_url = "https://openrouter.ai/api/v1/chat/completions"
            chat_payload = {
                "model": model,
                "messages": [{"role": "user", "content": f"Generate an image of: {prompt}"}]
            }
            
            chat_response = requests.post(chat_url, headers=headers, json=chat_payload, timeout=30)
            if chat_response.status_code == 200:
                chat_data = chat_response.json()
                logger.info(f"🔍 Full Chat Response: {json.dumps(chat_data)}") # Debug log
                
                # Save to debug file
                with open("debug_response.json", "w") as f:
                    json.dump(chat_data, f, indent=2)
                
                # Check for image in content (Markdown)
                content = chat_data["choices"][0]["message"]["content"]
                logger.info(f"✅ Chat response received: {content}")
                
                # 1. Try Markdown Image ![alt](url)
                import re
                md_match = re.search(r'!\[.*?\]\((https?://[^\)]+)\)', content)
                if md_match:
                    return md_match.group(1)

                # 2. Try just a URL in the text
                url_match = re.search(r'(https?://[^\s\)]+)', content)
                if url_match:
                    return url_match.group(1)
                
                # 3. Check for Google/Gemini specific "images" list in message
                try:
                    if "images" in chat_data["choices"][0]["message"]:
                        images = chat_data["choices"][0]["message"]["images"]
                        if images and len(images) > 0:
                            image_url = images[0].get("image_url", {}).get("url")
                            if image_url:
                                return image_url
                except Exception as e:
                    logger.warning(f"⚠️ Failed to extract image from message.images: {e}")

                logger.warning("⚠️ Could not extract URL from chat response.")
            else:
                logger.error(f"❌ Chat Endpoint also failed: {chat_response.text}")

    except Exception as e:
        logger.error(f"❌ Error generating image: {e}")

    return "https://placehold.co/1200x600?text=Image+Generation+Failed"
