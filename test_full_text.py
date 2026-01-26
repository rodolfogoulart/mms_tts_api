#!/usr/bin/env python3
"""
Test with the FULL text reported by user (2 verses)
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

def test_full_text():
    """Test with full user text (Genesis 1:1-8)"""
    print("\n" + "="*80)
    print("🔍 TEST: Full User Text (Genesis 1:1-8)")
    print("="*80)
    
    token = get_auth_token()
    
    text = """בְּרֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃ וְהָאָ֗רֶץ הָיְתָ֥ה תֹ֨הוּ֙ וָבֹ֔הוּ וְחֹ֖שֶׁךְ עַל־פְּנֵ֣י תְה֑וֹם וְר֣וּחַ אֱלֹהִ֔ים מְרַחֶ֖פֶת עַל־פְּנֵ֥י הַמָּֽיִם׃ וַיֹּ֥אמֶר אֱלֹהִ֖ים יְהִ֣י א֑וֹר וַֽיְהִי־אֽוֹר׃ וַיַּ֧רְא אֱלֹהִ֛ים אֶת־הָא֖וֹר כִּי־ט֑וֹב וַיַּבְדֵּ֣ל אֱלֹהִ֔ים בֵּ֥ין הָא֖וֹר וּבֵ֥ין הַחֹֽשֶׁךְ׃ וַיִּקְרָ֨א אֱלֹהִ֤ים ׀ לָאוֹר֙ י֔וֹם וְלַחֹ֖שֶׁךְ קָ֣רָא לָ֑יְלָה וַֽיְהִי־עֶ֥רֶב וַֽיְהִי־בֹ֖קֶר י֥וֹם אֶחָֽד׃ פ
וַיֹּ֣אמֶר אֱלֹהִ֔ים יְהִ֥י רָקִ֖יעַ בְּת֣וֹךְ הַמָּ֑יִם וִיהִ֣י מַבְדִּ֔יל בֵּ֥ין מַ֖יִם לָמָֽיִם׃ וַיַּ֣עַשׂ אֱלֹהִים֮ אֶת־הָרָקִיעַ֒ וַיַּבְדֵּ֗ל בֵּ֤ין הַמַּ֨יִם֙ אֲשֶׁר֙ מִתַּ֣חַת לָרָקִ֔יעַ וּבֵ֣ין הַמַּ֔יִם אֲשֶׁ֖ר מֵעַ֣ל לָרָקִ֑יעַ וַֽיְהִי־כֵֽן׃ וַיִּקְרָ֧א אֱלֹהִ֛ים לָֽרָקִ֖יעַ שָׁמָ֑יִם וַֽיְהִי־עֶ֥רֶב וַֽיְהִי־בֹ֖קֶר י֥וֹם שֵׁנִֽי׃ פ"""
    
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
        
        # Save files
        os.makedirs("test_output", exist_ok=True)
        
        # Save audio
        audio_bytes = base64.b64decode(result['audio_base64'])
        with open("test_output/full_text.mp3", "wb") as f:
            f.write(audio_bytes)
        
        # Save JSON
        with open("test_output/full_text.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # Analyze timestamps
        print("\n📊 TIMESTAMP ANALYSIS:")
        print("-" * 90)
        print(f"{'#':<4} {'Palavra':<25} {'Início (s)':<12} {'Fim (s)':<12} {'Duração':<10} {'Conf':<6}")
        print("-" * 90)
        
        fixed_duration_count = 0
        variable_duration_count = 0
        missing_count = 0
        durations_set = set()
        
        for i, word in enumerate(result['word_timestamps'][:20], 1):  # First 20
            duration = word['end'] - word['start'] if word['start'] >= 0 else 0
            
            if word['start'] < 0:
                missing_count += 1
                status = "❌ MISSING"
            else:
                durations_set.add(round(duration, 3))
                if duration > 0:
                    variable_duration_count += 1
                status = "✅"
            
            print(f"{i:<4} {word['text'][:25]:<25} {word['start']:<12.3f} {word['end']:<12.3f} {duration:<10.3f} {word['confidence']:<6.2f} {status}")
        
        print("-" * 90)
        print(f"\n📈 Statistics:")
        print(f"   - Total words: {len(result['word_timestamps'])}")
        print(f"   - Missing timestamps: {missing_count}")
        print(f"   - Unique durations: {len(durations_set)}")
        
        if len(durations_set) == 1 and missing_count == 0:
            print(f"   ⚠️  ALL DURATIONS IDENTICAL = FALLBACK MODE (not real timestamps!)")
        elif missing_count > len(result['word_timestamps']) * 0.3:
            print(f"   ⚠️  HIGH MISS RATE: {missing_count}/{len(result['word_timestamps'])} ({100*missing_count/len(result['word_timestamps']):.1f}%)")
        else:
            print(f"   ✅ Whisper timestamps working ({100*(1-missing_count/len(result['word_timestamps'])):.1f}% matched)")
        
        print(f"\n📁 Files saved:")
        print(f"   - test_output/full_text.mp3")
        print(f"   - test_output/full_text.json")
        
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_full_text()
