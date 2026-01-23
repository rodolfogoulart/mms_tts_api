#!/usr/bin/env python3
"""
Test script for Sherpa-ONNX TTS API
Tests Portuguese, Hebrew, and Greek models using docker-compose.local.yml
"""
import requests
import json
import time
from pathlib import Path

API_URL = "http://localhost:8000"
# Default credentials from docker-compose.local.yml
USERNAME = "demo"
PASSWORD = "demo123"

def login():
    """Login and get access token"""
    print("\n🔐 Logging in...")
    response = requests.post(
        f"{API_URL}/auth/login",
        data={
            "username": USERNAME,
            "password": PASSWORD
        }
    )
    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"✅ Logged in as: {USERNAME}")
        return token
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(f"   Error: {response.text}")
        return None

def test_health():
    """Test health endpoint"""
    print("\n" + "="*60)
    print("Testing Health Endpoint")
    print("="*60)
    
    response = requests.get(f"{API_URL}/health")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Status: {data['status']}")
        print(f"✅ Version: {data['version']}")
        print(f"✅ Engine: {data['engine']}")
        print(f"✅ Loaded models: {data['loaded_models']}")
        return True
    else:
        print(f"❌ Health check failed: {response.status_code}")
        return False

def test_tts(text, model, language_name, output_file, token):
    """Test TTS generation"""
    print(f"\n📝 Testing {language_name}")
    print(f"   Text: {text[:50]}...")
    print(f"   Model: {model}")
    
    start = time.time()
    
    response = requests.post(
        f"{API_URL}/speak",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "text": text,
            "model": model,
            "speed": 1.0,
            "output_format": "mp3"
        }
    )
    
    elapsed = time.time() - start
    
    if response.status_code == 200:
        # Save audio file
        with open(output_file, 'wb') as f:
            f.write(response.content)
        
        file_size = len(response.content) / 1024  # KB
        print(f"   ✅ Generated in {elapsed:.2f}s")
        print(f"   ✅ File size: {file_size:.1f} KB")
        print(f"   ✅ Saved to: {output_file}")
        return True
    else:
        print(f"   ❌ Failed: {response.status_code}")
        print(f"   Error: {response.text}")
        return False

def test_models_list():
    """Test models listing"""
    print("\n" + "="*60)
    print("Testing Models List")
    print("="*60)
    
    response = requests.get(f"{API_URL}/models")
    if response.status_code == 200:
        data = response.json()
        print("✅ Available models:")
        for name, info in data['models'].items():
            loaded = "🟢 LOADED" if info['loaded'] else "⚪ Not loaded"
            print(f"   - {name}: {info['name']} {loaded}")
        return True
    else:
        print(f"❌ Failed to list models: {response.status_code}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 SHERPA-ONNX TTS API TESTS")
    print("   Using: docker-compose.local.yml")
    print("="*60)
    
    # Create output directory
    output_dir = Path("./docker_test_output")
    output_dir.mkdir(exist_ok=True)
    
    # Login first
    token = login()
    if not token:
        print("\n❌ Login failed. Exiting.")
        return
    
    time.sleep(1)
    
    # Test 1: Health check
    if not test_health():
        print("\n❌ Health check failed. Exiting.")
        return
    
    time.sleep(1)
    
    # Test 2: List models
    if not test_models_list():
        print("\n⚠️ Failed to list models, but continuing...")
    
    time.sleep(1)
    
    # Test 3: Portuguese TTS
    print("\n" + "="*60)
    print("Testing Portuguese TTS (Genesis 1:1)")
    print("="*60)
    test_tts(
        text="No princípio, Deus criou os céus e a terra.",
        model="portuguese",
        language_name="Portuguese",
        output_file=output_dir / "test_portuguese_sherpa.mp3",
        token=token
    )
    
    time.sleep(2)
    
    # Test 4: Hebrew TTS
    print("\n" + "="*60)
    print("Testing Hebrew TTS (Genesis 1:1)")
    print("="*60)
    test_tts(
        text="בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ",
        model="hebrew",
        language_name="Hebrew",
        output_file=output_dir / "test_hebrew_sherpa.mp3",
        token=token
    )
    
    time.sleep(2)
    
    # Test 5: Greek TTS
    print("\n" + "="*60)
    print("Testing Greek TTS (Genesis 1:1)")
    print("="*60)
    test_tts(
        text="Ἐν ἀρχῇ ἐποίησεν ὁ θεὸς τὸν οὐρανὸν καὶ τὴν γῆν",
        model="greek",
        language_name="Greek",
        output_file=output_dir / "test_greek_sherpa.mp3",
        token=token
    )
    
    print("\n" + "="*60)
    print("🎉 ALL TESTS COMPLETED!")
    print("="*60)
    print(f"\n📁 Audio files saved in: {output_dir.absolute()}")
    print("\n💡 Next steps:")
    print("   1. Listen to the generated MP3 files")
    print("   2. Compare with previous ONNX Runtime output")
    print("   3. Verify audio quality is now correct")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
