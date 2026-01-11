import json
import os
from portfolio_manager import PortfolioManagerAgent
from product_manager import ProductManagerAgent

def run_pipeline(topic):
    print(f"🚀 Starting Content Pipeline for: {topic}")
    
    # 1. Portfolio Manager finds and analyzes products
    portfolio_mgr = PortfolioManagerAgent()
    recommendations = portfolio_mgr.analyze_and_recommend(topic)
    
    if not recommendations:
        print("❌ Pipeline failed: No recommendations found.")
        return

    # 2. Product Manager creates the content
    product_mgr = ProductManagerAgent()
    article_data = product_mgr.create_content(topic, recommendations)
    
    if not article_data:
        print("❌ Pipeline failed: Content generation failed.")
        return

    # 3. Save to Frontend Content Directory
    output_dir = "../frontend/content"
    os.makedirs(output_dir, exist_ok=True)
    
    # Load existing posts or create new list
    posts_file = os.path.join(output_dir, "posts.json")
    posts = []
    if os.path.exists(posts_file):
        with open(posts_file, "r") as f:
            try:
                posts = json.load(f)
            except json.JSONDecodeError:
                posts = []
    
    # Append new post (avoid duplicates based on slug in a real app, simple append for now)
    posts.append(article_data)
    
    with open(posts_file, "w") as f:
        json.dump(posts, f, indent=2)
        
    print(f"✅ Content generated and saved to {posts_file}")
    print(f"📄 Title: {article_data.get('title')}")

if __name__ == "__main__":
    # Example topics to generate content for
    topics = [
        "melhores notebooks gamer custo beneficio",
        "melhores fones de ouvido bluetooth cancelamento de ruido"
    ]
    
    for topic in topics:
        run_pipeline(topic)
