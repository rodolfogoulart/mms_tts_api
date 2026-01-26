#!/usr/bin/env python3
"""
Test script para validar as melhorias no fuzzy matching
Testa o mesmo texto que teve 50% de match rate
"""
import requests
import json
import sys

def test_alignment():
    """Test alignment com texto que teve problemas"""
    
    # Texto que teve apenas 6/12 palavras matched (50%)
    text = "וְהָאָ֗רֶץ הָיְתָ֥ה תֹ֨הוּ֙ וָבֹ֔הוּ וְחֹ֖שֶׁךְ עַל־פְּנֵ֣י תְהֹ֑ום וְר֣וּחַ אֱלֹהִ֔ים מְרַחֶ֖פֶת עַל־פְּנֵ֥י הַמָּֽיִם׃"
    
    print("🧪 Test: Improved fuzzy matching")
    print("=" * 60)
    print(f"Text: {text}")
    print(f"Words: {len(text.split())}")
    print()
    
    # Send request
    url = "http://localhost:8000/speak_sync"
    headers = {
        "X-API-Key": "demo-api-key-12345"  # Demo API key
    }
    payload = {
        "text": text,
        "language": "hebrew"
    }
    
    print("⏳ Sending request...")
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False
    
    result = response.json()
    
    # Analyze results
    word_timestamps = result.get('word_timestamps', [])
    alignment_stats = result.get('alignment_stats', {})
    
    print("\n📊 Results:")
    print("=" * 60)
    print(f"Total words: {len(word_timestamps)}")
    print(f"Match rate: {alignment_stats.get('match_ratio', 0):.1%}")
    print(f"Matched words: {alignment_stats.get('matched_count', 0)}/{len(word_timestamps)}")
    print()
    
    # Show confidence distribution
    confidences = [w['confidence'] for w in word_timestamps]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    
    high_conf = sum(1 for c in confidences if c >= 0.8)
    medium_conf = sum(1 for c in confidences if 0.5 <= c < 0.8)
    low_conf = sum(1 for c in confidences if c < 0.5)
    
    print("🎯 Confidence Distribution:")
    print(f"  High (≥0.8):   {high_conf} words ({high_conf/len(confidences)*100:.1f}%)")
    print(f"  Medium (0.5-0.8): {medium_conf} words ({medium_conf/len(confidences)*100:.1f}%)")
    print(f"  Low (<0.5):    {low_conf} words ({low_conf/len(confidences)*100:.1f}%)")
    print(f"  Average:       {avg_conf:.2f}")
    print()
    
    # Show word details
    print("📝 Word Details:")
    print("-" * 60)
    for i, word in enumerate(word_timestamps):
        duration = word['end'] - word['start']
        conf_color = "🟢" if word['confidence'] >= 0.8 else "🟡" if word['confidence'] >= 0.5 else "🔴"
        print(f"{i+1:2d}. {conf_color} {word['word']:15s} [{word['start']:.2f}-{word['end']:.2f}s] "
              f"({duration:.2f}s) conf={word['confidence']:.2f}")
    
    # Check for improvements
    print("\n✨ Results:")
    print("=" * 60)
    
    match_rate = alignment_stats.get('match_ratio', 0)
    if match_rate >= 0.90:
        print(f"✅ EXCELLENT: {match_rate:.1%} match rate (target: ≥90%)")
        return True
    elif match_rate >= 0.75:
        print(f"✅ GOOD: {match_rate:.1%} match rate (improved from 50%)")
        return True
    elif match_rate > 0.50:
        print(f"⚠️  IMPROVED: {match_rate:.1%} match rate (was 50%, but not at target yet)")
        return True
    else:
        print(f"❌ NO IMPROVEMENT: {match_rate:.1%} match rate (still at 50%)")
        return False

if __name__ == "__main__":
    try:
        success = test_alignment()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
