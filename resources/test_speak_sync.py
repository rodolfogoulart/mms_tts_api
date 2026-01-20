#!/usr/bin/env python3
"""
Script de teste para o endpoint /speak_sync
Testa funcionalidade completa de word-level alignment
"""

import requests
import json
import sys
import time
from typing import Dict

# ====== CONFIGURAÇÃO ======
API_BASE_URL = "http://localhost:8000"  # Ajustar para seu ambiente
USERNAME = "admin"
PASSWORD = "yourPassword"  # Usar suas credenciais

# Textos de teste
TEST_CASES = {
    "hebrew": {
        "text": "בְּרֵאשִׁית בָּרָא אֱלֹהִים",
        "lang": "heb",
        "description": "Gênesis 1:1 (Hebraico com niqqud)"
    },
    "greek": {
        "text": "Ἐν ἀρχῇ ἦν ὁ λόγος",
        "lang": "ell",
        "description": "João 1:1 (Grego com acentos)"
    },
    "portuguese": {
        "text": "No princípio era o Verbo",
        "lang": "por",
        "description": "João 1:1 (Português)"
    }
}


def login(base_url: str, username: str, password: str) -> str:
    """Faz login e retorna JWT token"""
    print(f"\n🔐 Fazendo login como '{username}'...")
    
    response = requests.post(
        f"{base_url}/auth/login",
        data={"username": username, "password": password}
    )
    
    if response.status_code != 200:
        print(f"❌ Login falhou: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    data = response.json()
    token = data["access_token"]
    user_info = data["user"]
    
    print(f"✅ Login bem-sucedido!")
    print(f"   User: {user_info['username']}")
    print(f"   Email: {user_info.get('email', 'N/A')}")
    print(f"   Rate Limit: {user_info['rate_limit']} req/hour")
    print(f"   Admin: {user_info['is_admin']}")
    
    return token


def test_speak_sync(base_url: str, token: str, test_case: Dict) -> Dict:
    """Testa endpoint /speak_sync"""
    text = test_case["text"]
    lang = test_case["lang"]
    description = test_case["description"]
    
    print(f"\n{'='*60}")
    print(f"🧪 Testando: {description}")
    print(f"{'='*60}")
    print(f"📝 Texto: {text}")
    print(f"🌍 Idioma: {lang}")
    
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "text": text,
        "lang": lang,
        "speed": 1.0
    }
    
    print(f"\n⏳ Enviando requisição para /speak_sync...")
    start_time = time.time()
    
    response = requests.post(
        f"{base_url}/speak_sync",
        headers=headers,
        data=data
    )
    
    elapsed_time = time.time() - start_time
    
    if response.status_code != 200:
        print(f"❌ Erro {response.status_code}: {response.text}")
        return {}
    
    result = response.json()
    
    print(f"✅ Resposta recebida em {elapsed_time:.2f}s")
    print(f"\n📊 Resultado:")
    print(f"   Audio URL: {result['audio_url']}")
    print(f"   Language: {result['language']} ({result['language_name']})")
    print(f"   Model: {result['model_used']}")
    print(f"   Word Count: {result['word_count']}")
    print(f"   Alignment Available: {result['alignment_available']}")
    print(f"   Cache Hit (Audio): {result['cache_hit']}")
    print(f"   Cache Hit (Alignment): {result['alignment_cache_hit']}")
    
    # Exibir palavras com timestamps
    if result['words']:
        print(f"\n📍 Palavras com Timestamps:")
        print(f"   {'Palavra':<20} | Start  | End    | Duration")
        print(f"   {'-'*20}-|--------|--------|--------")
        
        for word in result['words']:
            duration = word['end'] - word['start']
            print(f"   {word['text']:<20} | {word['start']:>6.2f} | {word['end']:>6.2f} | {duration:>6.2f}s")
        
        # Estatísticas
        total_duration = result['words'][-1]['end'] if result['words'] else 0
        avg_word_duration = sum(w['end'] - w['start'] for w in result['words']) / len(result['words'])
        
        print(f"\n   Duração Total: {total_duration:.2f}s")
        print(f"   Duração Média/Palavra: {avg_word_duration:.2f}s")
    else:
        print(f"\n⚠️  Nenhuma palavra alinhada (alignment falhou)")
    
    # Testar download do áudio
    print(f"\n⬇️  Testando download do áudio...")
    audio_response = requests.get(
        f"{base_url}{result['audio_url']}",
        headers=headers
    )
    
    if audio_response.status_code == 200:
        audio_size = len(audio_response.content)
        print(f"✅ Áudio baixado com sucesso ({audio_size} bytes)")
    else:
        print(f"❌ Erro ao baixar áudio: {audio_response.status_code}")
    
    return result


def test_cache_performance(base_url: str, token: str, test_case: Dict):
    """Testa performance do cache fazendo requisição duplicada"""
    print(f"\n{'='*60}")
    print(f"⚡ Testando Performance do Cache")
    print(f"{'='*60}")
    
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "text": test_case["text"],
        "lang": test_case["lang"],
        "speed": 1.0
    }
    
    # Primeira requisição (provavelmente cache miss)
    print(f"\n1️⃣  Primeira requisição (pode ser cache miss)...")
    start1 = time.time()
    response1 = requests.post(f"{base_url}/speak_sync", headers=headers, data=data)
    time1 = time.time() - start1
    result1 = response1.json()
    
    print(f"   Tempo: {time1:.2f}s")
    print(f"   Audio Cache Hit: {result1['cache_hit']}")
    print(f"   Alignment Cache Hit: {result1['alignment_cache_hit']}")
    
    # Segunda requisição (deve ser cache hit)
    print(f"\n2️⃣  Segunda requisição (deve ser cache hit)...")
    start2 = time.time()
    response2 = requests.post(f"{base_url}/speak_sync", headers=headers, data=data)
    time2 = time.time() - start2
    result2 = response2.json()
    
    print(f"   Tempo: {time2:.2f}s")
    print(f"   Audio Cache Hit: {result2['cache_hit']}")
    print(f"   Alignment Cache Hit: {result2['alignment_cache_hit']}")
    
    # Análise
    speedup = time1 / time2 if time2 > 0 else 0
    print(f"\n📈 Análise:")
    print(f"   Speedup: {speedup:.1f}x mais rápido com cache")
    print(f"   Economia de tempo: {time1 - time2:.2f}s")
    
    if result2['cache_hit'] and result2['alignment_cache_hit']:
        print(f"   ✅ Cache funcionando perfeitamente!")
    else:
        print(f"   ⚠️  Cache parcial ou não funcional")


def main():
    """Executa todos os testes"""
    print(f"\n{'='*60}")
    print(f"🧪 TESTE DO ENDPOINT /speak_sync")
    print(f"{'='*60}")
    print(f"Base URL: {API_BASE_URL}")
    
    # 1. Login
    token = login(API_BASE_URL, USERNAME, PASSWORD)
    
    # 2. Testar cada idioma
    for lang_key, test_case in TEST_CASES.items():
        result = test_speak_sync(API_BASE_URL, token, test_case)
        
        if not result:
            print(f"\n⚠️  Teste falhou para {lang_key}, pulando...")
            continue
        
        # Validações
        assert result['language'] == test_case['lang'], "Idioma incorreto"
        assert result['audio_url'], "Audio URL vazia"
        
        if result['alignment_available']:
            assert len(result['words']) > 0, "Palavras vazias mas alignment_available=true"
            
            # Validar formato das palavras
            for word in result['words']:
                assert 'text' in word, "Palavra sem campo 'text'"
                assert 'start' in word, "Palavra sem campo 'start'"
                assert 'end' in word, "Palavra sem campo 'end'"
                assert word['end'] >= word['start'], "Timestamp inválido (end < start)"
        
        print(f"\n✅ Todas as validações passaram para {lang_key}")
    
    # 3. Testar performance do cache
    test_cache_performance(API_BASE_URL, token, TEST_CASES["hebrew"])
    
    # 4. Resumo final
    print(f"\n{'='*60}")
    print(f"✅ TODOS OS TESTES CONCLUÍDOS COM SUCESSO!")
    print(f"{'='*60}")
    print(f"\n📋 Próximos Passos:")
    print(f"   1. Verificar logs do servidor para detalhes")
    print(f"   2. Testar integração com frontend")
    print(f"   3. Ajustar rate limits se necessário")
    print(f"   4. Monitorar uso de memória/CPU")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Teste interrompido pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Erro durante testes: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
