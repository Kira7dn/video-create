"""
Demo script để test PydanticAI Keyword Extraction
Chạy script này để thấy cách PydanticAI trích xuất keywords thông minh với type safety
"""
import os
import sys
import asyncio

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.processors.image_auto_processor import ImageAutoProcessor
from app.config.settings import settings

async def demo_pydantic_ai_keyword_extraction():
    """Demo PydanticAI keyword extraction với các test cases khác nhau"""
    
    print("🤖 PydanticAI Keyword Extraction Demo")
    print("=" * 50)
    
    # Test cases với nhiều ngữ cảnh khác nhau
    test_cases = [
        "A beautiful sunset over the ocean with waves crashing on the beach",
        "Business meeting in modern office with laptops and documents",
        "Chef cooking delicious pasta in professional kitchen",
        "Mountain hiking adventure with backpack and scenic views",
        "Technology startup team working on laptop coding",
        "Wedding ceremony with bride and groom exchanging rings",
        "Children playing in colorful playground during summer",
        "Coffee shop atmosphere with books and warm lighting"
    ]
    
    # Khởi tạo processor
    processor = ImageAutoProcessor()
    print(f"🔑 API Key: {'✅ Configured' if settings.openai_api_key else '❌ Missing'}")
    print(f"🤖 AI Model: {settings.ai_pydantic_model}")
    print(f"⚡ AI Enabled: {settings.ai_keyword_extraction_enabled}")
    print(f"📊 Max Keywords: {settings.ai_max_keywords_per_prompt}")
    print(f"🎯 Using: PydanticAI with structured output")
    print()
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"📝 Test Case {i}:")
        print(f"   Input: \"{test_case}\"")
        
        try:
            keywords = await processor._ai_extract_keywords(test_case)
            print(f"   🎯 Keywords: {keywords}")
            print(f"   🔍 Pixabay Ready: {', '.join(keywords[:3])}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()
    
    print("=" * 50)
    print("💡 Để sử dụng PydanticAI keyword extraction:")
    print("1. Cấu hình OPENAI_API_KEY trong .env file")
    print("2. Set AI_KEYWORD_EXTRACTION_ENABLED=true")
    print("3. Chọn model phù hợp (gpt-3.5-turbo khuyến nghị)")
    print("4. PydanticAI sẽ tự động validate output structure")

async def demo_simple_vs_pydantic_ai_comparison():
    """So sánh keyword extraction đơn giản vs PydanticAI"""
    
    print("\n🔬 Simple vs PydanticAI Keyword Comparison")
    print("=" * 50)
    
    test_text = "A professional business meeting in a modern office with laptops, documents, and teamwork collaboration"
    
    processor = ImageAutoProcessor()
    
    # Simple extraction (fallback)
    print(f"📝 Input: \"{test_text}\"")
    print()
    
    # Disable AI temporarily for comparison
    original_enabled = settings.ai_keyword_extraction_enabled
    settings.ai_keyword_extraction_enabled = False
    
    simple_keywords = await processor._ai_extract_keywords(test_text)
    print(f"🔤 Simple Keywords: {simple_keywords}")
    
    # Enable AI
    settings.ai_keyword_extraction_enabled = original_enabled
    
    if settings.openai_api_key:
        ai_keywords = await processor._ai_extract_keywords(test_text)
        print(f"🤖 PydanticAI Keywords: {ai_keywords}")
        
        print("\n📊 Analysis:")
        print(f"   Simple: {len(simple_keywords)} keywords")
        print(f"   PydanticAI: {len(ai_keywords)} keywords")
        print(f"   PydanticAI advantages: Type safety, structured output, better parsing")
    else:
        print("🤖 PydanticAI Keywords: ❌ Need API key")
        print("\n💡 Configure OPENAI_API_KEY to see PydanticAI enhancement")

async def main():
    """Main async function"""
    try:
        await demo_pydantic_ai_keyword_extraction()
        await demo_simple_vs_pydantic_ai_comparison()
    except KeyboardInterrupt:
        print("\n👋 Demo stopped by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
