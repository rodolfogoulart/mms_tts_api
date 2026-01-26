#!/usr/bin/env python3
"""
Debug test for forced alignment with detailed logging
"""
import requests
import json
import base64
import os

API_BASE_URL = "http://localhost:8000"

def get_auth_token():
    """Get JWT token for authentication"""
    response = requests.post(f"{API_BASE_URL}/auth/login", data={
        "username": "admin",
        "password": "admin123"
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Failed to get token: {response.status_code} {response.text}")

def test_hebrew_short():
    """Test with short Hebrew text (Genesis 1:1)"""
    print("\n" + "="*80)
    print("🔍 DEBUG TEST: Hebrew Short Text (Genesis 1:1)")
    print("="*80)
    
    token = get_auth_token()
    
    text = "בְּרֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃"
    
    response = requests.post(
        f"{API_BASE_URL}/speak_sync",
        data={
            "text": text,
            "model": "hebrew",
            "speed": 1.0,
            "output_format": "mp3",
            "return_audio": True
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"✅ Success!")
        print(f"Audio duration: {result['audio_duration']:.2f}s")
        print(f"Total words: {len(result['word_timestamps'])}")
        
        # Save audio
        audio_bytes = base64.b64decode(result['audio_base64'])
        os.makedirs("test_output", exist_ok=True)
        with open("test_output/debug_hebrew.mp3", "wb") as f:
            f.write(audio_bytes)
        
        # Analyze timestamps
        print("\n📊 TIMESTAMP ANALYSIS:")
        print("-" * 80)
        
        durations = []
        for i, word in enumerate(result['word_timestamps'][:10], 1):  # First 10 words
            duration = word['end'] - word['start']
            durations.append(duration)
            print(f"{i:2d}. '{word['text'][:20]:20s}' | {word['start']:.3f}s - {word['end']:.3f}s | Δ={duration:.3f}s | conf={word['confidence']:.2f}")
        
        # Check if all durations are identical (indicates fallback)
        if len(set(durations)) == 1:
            print("\n⚠️  WARNING: All durations are IDENTICAL - this indicates FALLBACK mode!")
            print(f"   All words have exactly {durations[0]:.3f}s duration")
            print("   This means Whisper did NOT return word timestamps!")
        else:
            print("\n✅ Durations vary - Whisper word timestamps are working correctly")
        
        # Save JSON for inspection
        with open("test_output/debug_hebrew.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n📁 Files saved:")
        print(f"   - test_output/debug_hebrew.mp3")
        print(f"   - test_output/debug_hebrew.json")
        
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_hebrew_short()
