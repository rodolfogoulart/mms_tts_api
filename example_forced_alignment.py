#!/usr/bin/env python3
"""
Exemplo simples de uso do endpoint /speak_sync
Demonstra geração de áudio + alinhamento palavra-por-palavra
"""

import requests
import json
import base64
from pathlib import Path

# Configuração
API_URL = "http://localhost:8000"

def forced_alignment_example():
    """Exemplo básico de forced alignment"""
    
    # Texto para converter
    text = "בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ"
    
    print("🎯 Forced Alignment - Exemplo Simples")
    print("=" * 60)
    print(f"Texto: {text}")
    print(f"Idioma: Hebraico\n")
    
    # Fazer requisição
    print("📡 Enviando requisição...")
    response = requests.post(f"{API_URL}/speak_sync", data={
        "text": text,
        "model": "hebrew",
        "speed": 1.0,
        "output_format": "mp3",
        "return_audio": True  # Retornar áudio em base64
    })
    
    response.raise_for_status()
    result = response.json()
    
    # Exibir resultados
    print("✅ Resposta recebida!\n")
    
    # 1. Informações gerais
    print("📊 Informações Gerais:")
    print(f"  - Duração: {result['audio_duration']:.2f}s")
    print(f"  - Formato: {result['audio_format']}")
    print(f"  - Velocidade: {result['speed']}x\n")
    
    # 2. Estatísticas de alinhamento
    stats = result['alignment_stats']
    print("📈 Estatísticas de Alinhamento:")
    print(f"  - Total de palavras: {stats['total_words']}")
    print(f"  - Palavras matched: {stats['matched_words']}")
    print(f"  - Taxa de match: {stats['match_ratio']:.1%}\n")
    
    # 3. Tempos de processamento
    proc = result['processing_time']
    print("⏱️  Tempos de Processamento:")
    print(f"  - TTS: {proc['tts_seconds']:.2f}s")
    print(f"  - Alinhamento: {proc['alignment_seconds']:.2f}s")
    print(f"  - Total: {proc['total_seconds']:.2f}s\n")
    
    # 4. Timestamps por palavra
    print("🎯 Timestamps por Palavra:")
    print(f"{'Palavra':<20} {'Início':<10} {'Fim':<10} {'Confiança'}")
    print("-" * 60)
    
    for word in result['word_timestamps']:
        conf_icon = "🟢" if word['confidence'] >= 0.8 else "🟡"
        print(f"{word['text']:<20} {word['start']:<10.2f} {word['end']:<10.2f} {conf_icon} {word['confidence']:.2f}")
    
    # 5. Salvar áudio
    if 'audio_base64' in result:
        output_dir = Path("example_output")
        output_dir.mkdir(exist_ok=True)
        
        audio_bytes = base64.b64decode(result['audio_base64'])
        audio_file = output_dir / "genesis_1_1.mp3"
        
        with open(audio_file, 'wb') as f:
            f.write(audio_bytes)
        
        print(f"\n💾 Áudio salvo: {audio_file}")
        
        # Salvar JSON com timestamps
        json_file = output_dir / "genesis_1_1_timestamps.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"📄 Timestamps salvos: {json_file}")


def highlight_example():
    """Exemplo de como usar timestamps para highlight"""
    
    print("\n" + "=" * 60)
    print("💡 Exemplo: Highlight Sincronizado")
    print("=" * 60)
    
    # Código exemplo
    code = '''
# Pseudocódigo para highlight sincronizado

def on_audio_timeupdate(current_time):
    """Callback quando o tempo do áudio muda"""
    
    # Encontrar palavra atual baseada no tempo
    current_word = None
    for word in word_timestamps:
        if word['start'] <= current_time <= word['end']:
            current_word = word
            break
    
    # Aplicar highlight
    if current_word:
        highlight_text(
            start_pos=current_word['textStart'],
            end_pos=current_word['textEnd']
        )

# Exemplo JavaScript
audio.addEventListener('timeupdate', () => {
  const currentTime = audio.currentTime;
  const currentWord = wordTimestamps.find(
    w => currentTime >= w.start && currentTime <= w.end
  );
  
  if (currentWord) {
    highlightWord(currentWord.textStart, currentWord.textEnd);
  }
});
'''
    
    print(code)


def srt_example():
    """Exemplo de geração de legendas SRT"""
    
    print("\n" + "=" * 60)
    print("💡 Exemplo: Geração de Legendas SRT")
    print("=" * 60)
    
    code = '''
def generate_srt(word_timestamps, output_file):
    """Gera arquivo SRT a partir dos timestamps"""
    
    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for i, word in enumerate(word_timestamps, 1):
            if word['start'] >= 0 and word['end'] >= 0:
                start = format_time(word['start'])
                end = format_time(word['end'])
                f.write(f"{i}\\n{start} --> {end}\\n{word['text']}\\n\\n")

# Usar
generate_srt(result['word_timestamps'], 'output.srt')
'''
    
    print(code)


def batch_example():
    """Exemplo de processamento em lote"""
    
    print("\n" + "=" * 60)
    print("💡 Exemplo: Processamento em Lote")
    print("=" * 60)
    
    code = '''
def process_batch(verses):
    """Processa múltiplos versículos"""
    
    results = []
    
    for verse in verses:
        print(f"Processando: {verse['ref']}")
        
        response = requests.post(f"{API_URL}/speak_sync", data={
            "text": verse['text'],
            "model": verse['language'],
            "return_audio": True
        })
        
        result = response.json()
        
        # Salvar áudio
        audio_bytes = base64.b64decode(result['audio_base64'])
        with open(f"{verse['ref']}.mp3", 'wb') as f:
            f.write(audio_bytes)
        
        # Salvar timestamps
        with open(f"{verse['ref']}_timestamps.json", 'w') as f:
            json.dump(result['word_timestamps'], f, ensure_ascii=False, indent=2)
        
        results.append({
            'ref': verse['ref'],
            'quality': result['alignment_stats']['match_ratio']
        })
    
    return results

# Usar
verses = [
    {'ref': 'Gen1.1', 'text': 'בְּרֵאשִׁית...', 'language': 'hebrew'},
    {'ref': 'John1.1', 'text': 'Ἐν ἀρχῇ...', 'language': 'greek'},
]

results = process_batch(verses)
'''
    
    print(code)


def main():
    """Função principal"""
    
    try:
        # 1. Exemplo básico
        forced_alignment_example()
        
        # 2. Exemplos de código
        highlight_example()
        srt_example()
        batch_example()
        
        print("\n" + "=" * 60)
        print("✅ Exemplo concluído com sucesso!")
        print("=" * 60)
        print("\n📚 Documentação completa: FORCED_ALIGNMENT.md")
        print("🎨 Demo interativo: demo_forced_alignment.html")
        print("🧪 Testes: test_forced_alignment.py")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Erro: Não foi possível conectar à API")
        print("\n💡 Certifique-se de que a API está rodando:")
        print("   docker-compose -f docker-compose.local.yml up -d")
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")


if __name__ == "__main__":
    main()
