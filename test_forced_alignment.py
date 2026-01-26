#!/usr/bin/env python3
"""
Script de teste para o endpoint /speak_sync (Forced Alignment)
Testa geração de áudio + alinhamento palavra-por-palavra
"""

import requests
import json
import base64
import os
from pathlib import Path

# Configuração
API_URL = os.getenv("API_URL", "http://localhost:8000")
OUTPUT_DIR = Path("test_output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Credenciais de teste
USERNAME = os.getenv("API_USERNAME", "demo")
PASSWORD = os.getenv("API_PASSWORD", "demo123")

# Token de autenticação (será obtido no login)
_auth_token = None

def get_auth_token():
    """Obtém token de autenticação"""
    global _auth_token
    
    if _auth_token:
        return _auth_token
    
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            data={"username": USERNAME, "password": PASSWORD},
            timeout=10
        )
        response.raise_for_status()
        _auth_token = response.json()["access_token"]
        return _auth_token
    except Exception as e:
        print(f"⚠️  Falha ao obter token: {e}")
        return None

# Textos de teste para cada idioma
TEST_CASES = [
    {
        "name": "hebrew_genesis",
        "text": "בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ",
        "model": "hebrew",
        "description": "Gênesis 1:1 (Hebraico)"
    },
    {
        "name": "greek_john",
        "text": "Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν",
        "model": "greek",
        "description": "João 1:1 (Grego)"
    },
    {
        "name": "portuguese_psalm",
        "text": "O Senhor é o meu pastor e nada me faltará",
        "model": "portuguese",
        "description": "Salmo 23:1 (Português)"
    }
]

def test_forced_alignment(test_case: dict):
    """Testa o endpoint /speak_sync com um caso de teste"""
    print(f"\n{'='*70}")
    print(f"📝 Testando: {test_case['description']}")
    print(f"{'='*70}")
    print(f"Texto: {test_case['text']}")
    print(f"Modelo: {test_case['model']}")
    
    # Preparar requisição
    data = {
        "text": test_case["text"],
        "model": test_case["model"],
        "speed": 1.0,
        "output_format": "mp3",
        "return_audio": True
    }
    
    print(f"\n🚀 Enviando requisição para {API_URL}/speak_sync...")
    
    try:
        # Obter token de autenticação
        token = get_auth_token()
        if not token:
            print(f"❌ ERRO: Não foi possível autenticar")
            return False
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        response = requests.post(f"{API_URL}/speak_sync", data=data, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        # Estatísticas gerais
        print(f"\n✅ Resposta recebida com sucesso!")
        print(f"\n📊 Estatísticas:")
        print(f"   - Duração do áudio: {result['audio_duration']:.2f}s")
        print(f"   - Formato: {result.get('audio_format', 'N/A')}")
        print(f"   - Total de palavras: {result['alignment_stats']['total_words']}")
        print(f"   - Palavras matched: {result['alignment_stats']['matched_words']}")
        print(f"   - Taxa de match: {result['alignment_stats']['match_ratio']:.1%}")
        
        # Tempos de processamento
        proc_time = result['processing_time']
        print(f"\n⏱️  Tempos de Processamento:")
        print(f"   - TTS: {proc_time['tts_seconds']:.2f}s")
        print(f"   - Alinhamento: {proc_time['alignment_seconds']:.2f}s")
        print(f"   - Total: {proc_time['total_seconds']:.2f}s")
        
        # Detalhes dos timestamps
        print(f"\n🎯 Timestamps por Palavra:")
        print(f"{'Palavra':<30} {'Início':<10} {'Fim':<10} {'Confiança':<12}")
        print(f"{'-'*62}")
        
        for word in result['word_timestamps']:
            confidence_icon = "🟢" if word['confidence'] >= 0.8 else "🟡" if word['confidence'] >= 0.5 else "🔴"
            print(f"{word['text']:<30} {word['start']:<10.2f} {word['end']:<10.2f} {confidence_icon} {word['confidence']:<.2f}")
        
        # Salvar áudio se disponível
        if 'audio_base64' in result:
            audio_bytes = base64.b64decode(result['audio_base64'])
            output_file = OUTPUT_DIR / f"{test_case['name']}.mp3"
            with open(output_file, 'wb') as f:
                f.write(audio_bytes)
            print(f"\n💾 Áudio salvo: {output_file}")
        
        # Salvar JSON com timestamps
        json_file = OUTPUT_DIR / f"{test_case['name']}_timestamps.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"📄 Timestamps salvos: {json_file}")
        
        # Gerar arquivo SRT (legendas)
        srt_file = OUTPUT_DIR / f"{test_case['name']}.srt"
        generate_srt(result['word_timestamps'], srt_file)
        print(f"📝 Legendas SRT salvas: {srt_file}")
        
        # Análise de qualidade
        print(f"\n📈 Análise de Qualidade:")
        match_ratio = result['alignment_stats']['match_ratio']
        
        if match_ratio >= 0.9:
            print(f"   ✅ EXCELENTE - Alta precisão no alinhamento")
        elif match_ratio >= 0.7:
            print(f"   🟡 BOA - Alinhamento confiável")
        elif match_ratio >= 0.5:
            print(f"   ⚠️  RAZOÁVEL - Algumas palavras estimadas")
        else:
            print(f"   ❌ BAIXA - Usando timestamps estimados (fallback)")
        
        # Identificar palavras problemáticas
        low_conf_words = [w for w in result['word_timestamps'] if w['confidence'] < 0.7]
        if low_conf_words:
            print(f"\n⚠️  Palavras com baixa confiança ({len(low_conf_words)}):")
            for word in low_conf_words[:5]:  # Mostrar até 5
                print(f"   - '{word['text']}' (confiança: {word['confidence']:.2f})")
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"❌ ERRO: Timeout após 60s (requisição muito lenta)")
        return False
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ ERRO HTTP: {e}")
        if hasattr(e.response, 'text'):
            print(f"   Detalhes: {e.response.text}")
        return False
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return False


def generate_srt(word_timestamps: list, output_file: Path):
    """Gera arquivo SRT (legendas) a partir dos timestamps"""
    def format_timestamp(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    srt_content = []
    for i, word in enumerate(word_timestamps, 1):
        if word['start'] >= 0 and word['end'] >= 0:  # Apenas palavras com timestamps
            start = format_timestamp(word['start'])
            end = format_timestamp(word['end'])
            srt_content.append(f"{i}\n{start} --> {end}\n{word['text']}\n")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(srt_content))


def test_health_check():
    """Testa o health check da API"""
    print(f"\n{'='*70}")
    print(f"🏥 Testando Health Check")
    print(f"{'='*70}")
    
    try:
        response = requests.get(f"{API_URL}/health", timeout=10)
        response.raise_for_status()
        health = response.json()
        
        print(f"✅ API está funcionando!")
        print(f"   Status: {health['status']}")
        print(f"   Versão: {health['version']}")
        print(f"   Engine: {health['engine']}")
        print(f"   Modelos carregados: {', '.join(health['loaded_models'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ API não está respondendo: {e}")
        print(f"\n💡 Certifique-se de que a API está rodando:")
        print(f"   docker-compose -f docker-compose.local.yml up -d")
        return False


def main():
    """Função principal"""
    print(f"{'='*70}")
    print(f"🧪 TESTE DE FORCED ALIGNMENT - /speak_sync")
    print(f"{'='*70}")
    print(f"API URL: {API_URL}")
    print(f"Output: {OUTPUT_DIR}")
    
    # 1. Verificar health check
    if not test_health_check():
        print(f"\n❌ Abortando testes - API não disponível")
        return
    
    # 2. Executar testes
    results = []
    for test_case in TEST_CASES:
        success = test_forced_alignment(test_case)
        results.append((test_case['name'], success))
    
    # 3. Resumo final
    print(f"\n{'='*70}")
    print(f"📊 RESUMO DOS TESTES")
    print(f"{'='*70}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"   {status}: {name}")
    
    print(f"\n{'='*70}")
    print(f"🎯 Resultado Final: {passed}/{total} testes passaram")
    
    if passed == total:
        print(f"✅ TODOS OS TESTES PASSARAM!")
        print(f"\n💡 Arquivos gerados em: {OUTPUT_DIR}/")
        print(f"   - Áudios MP3")
        print(f"   - JSONs com timestamps")
        print(f"   - Arquivos SRT (legendas)")
    else:
        print(f"❌ ALGUNS TESTES FALHARAM")
    
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
