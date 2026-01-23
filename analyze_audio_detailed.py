#!/usr/bin/env python3
"""
Análise detalhada dos áudios gerados - verifica amplitude, silêncio, etc
"""
import numpy as np
from scipy.io import wavfile
from pydub import AudioSegment
import json

def analyze_audio_file(filename):
    """Análise detalhada de arquivo MP3"""
    print(f"\n{'='*60}")
    print(f"ANALISANDO: {filename}")
    print(f"{'='*60}")
    
    # Carregar MP3
    audio = AudioSegment.from_mp3(filename)
    
    # Converter para numpy array
    samples = np.array(audio.get_array_of_samples())
    if audio.channels == 2:
        samples = samples.reshape((-1, 2))
        samples = samples.mean(axis=1)  # Converter para mono
    
    # Normalizar para -1.0 a 1.0
    samples = samples.astype(np.float32) / 32768.0
    
    # Estatísticas básicas
    duration = len(audio) / 1000.0
    sample_rate = audio.frame_rate
    
    print(f"\n📊 Propriedades Básicas:")
    print(f"   Duração: {duration:.2f}s")
    print(f"   Sample rate: {sample_rate} Hz")
    print(f"   Samples: {len(samples):,}")
    print(f"   Channels: {audio.channels}")
    
    # Análise de amplitude
    amplitude_min = float(samples.min())
    amplitude_max = float(samples.max())
    amplitude_mean = float(samples.mean())
    amplitude_std = float(samples.std())
    amplitude_rms = float(np.sqrt(np.mean(samples**2)))
    amplitude_range = amplitude_max - amplitude_min
    
    print(f"\n🔊 Análise de Amplitude:")
    print(f"   Min: {amplitude_min:+.4f}")
    print(f"   Max: {amplitude_max:+.4f}")
    print(f"   Range: {amplitude_range:.4f}")
    print(f"   Mean: {amplitude_mean:+.4f}")
    print(f"   Std: {amplitude_std:.4f}")
    print(f"   RMS: {amplitude_rms:.4f}")
    
    # Verificar problemas
    print(f"\n⚠️  Diagnóstico:")
    if amplitude_range < 0.2:
        print(f"   ❌ PROBLEMA: Amplitude muito baixa ({amplitude_range:.4f})")
        print(f"      Deveria ser > 0.5 para boa qualidade")
        print(f"      Áudio quase inaudível!")
    elif amplitude_range < 0.5:
        print(f"   ⚠️  ATENÇÃO: Amplitude baixa ({amplitude_range:.4f})")
        print(f"      Áudio pode estar com volume baixo")
    else:
        print(f"   ✅ Amplitude OK ({amplitude_range:.4f})")
    
    # Análise de silêncio
    silence_threshold = 0.01  # Threshold para considerar silêncio
    non_silent_samples = np.abs(samples) > silence_threshold
    non_silent_percent = (non_silent_samples.sum() / len(samples)) * 100
    silent_percent = 100 - non_silent_percent
    
    print(f"\n🔇 Análise de Silêncio:")
    print(f"   Silêncio: {silent_percent:.1f}%")
    print(f"   Áudio: {non_silent_percent:.1f}%")
    
    if silent_percent > 80:
        print(f"   ❌ PROBLEMA: Muito silêncio ({silent_percent:.1f}%)")
    elif silent_percent > 50:
        print(f"   ⚠️  ATENÇÃO: Silêncio alto ({silent_percent:.1f}%)")
    else:
        print(f"   ✅ Silêncio OK ({silent_percent:.1f}%)")
    
    # Análise de picos
    peaks_above_half = (np.abs(samples) > 0.5).sum()
    peaks_above_quarter = (np.abs(samples) > 0.25).sum()
    peaks_above_tenth = (np.abs(samples) > 0.1).sum()
    
    print(f"\n📈 Análise de Picos:")
    print(f"   Samples > 0.5: {peaks_above_half:,} ({peaks_above_half/len(samples)*100:.2f}%)")
    print(f"   Samples > 0.25: {peaks_above_quarter:,} ({peaks_above_quarter/len(samples)*100:.2f}%)")
    print(f"   Samples > 0.1: {peaks_above_tenth:,} ({peaks_above_tenth/len(samples)*100:.2f}%)")
    
    # Criar versão normalizada para comparação
    if amplitude_range > 0:
        normalized_samples = samples / amplitude_range
        normalized_filename = filename.replace('.mp3', '_normalized.mp3')
        
        # Converter de volta para int16
        normalized_int16 = (normalized_samples * 32767 * 0.8).astype(np.int16)
        
        # Salvar como WAV temporário
        temp_wav = filename.replace('.mp3', '_temp.wav')
        wavfile.write(temp_wav, sample_rate, normalized_int16)
        
        # Converter para MP3
        normalized_audio = AudioSegment.from_wav(temp_wav)
        normalized_audio.export(normalized_filename, format='mp3', bitrate='128k')
        
        import os
        os.remove(temp_wav)
        
        print(f"\n💾 Versão normalizada salva: {normalized_filename}")
        print(f"   (Amplifique o áudio original para máximo volume)")
    
    return {
        "filename": filename,
        "duration": duration,
        "sample_rate": sample_rate,
        "amplitude_range": amplitude_range,
        "amplitude_rms": amplitude_rms,
        "silent_percent": silent_percent,
        "has_problem": amplitude_range < 0.2
    }

if __name__ == "__main__":
    import sys
    
    files = [
        "genesis_portuguese.mp3",
        "genesis_hebrew.mp3", 
        "genesis_greek.mp3"
    ]
    
    results = []
    for f in files:
        try:
            result = analyze_audio_file(f)
            results.append(result)
        except Exception as e:
            print(f"\n❌ Erro ao analisar {f}: {e}")
    
    # Comparação
    print(f"\n\n{'='*60}")
    print("COMPARAÇÃO FINAL")
    print(f"{'='*60}")
    
    for r in results:
        status = "❌ PROBLEMA" if r["has_problem"] else "✅ OK"
        print(f"\n{r['filename']}:")
        print(f"  Status: {status}")
        print(f"  Amplitude: {r['amplitude_range']:.4f}")
        print(f"  RMS: {r['amplitude_rms']:.4f}")
        print(f"  Silêncio: {r['silent_percent']:.1f}%")
        print(f"  Duração: {r['duration']:.2f}s")
