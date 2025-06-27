#!/usr/bin/env python3
"""
Teste específico para modelos TTS de Hebraico e Grego apenas
"""
import requests
import json
import time

def test_hebrew_greek_api():
    base_url = "http://localhost:3000"
    
    print("🇮🇱🇬🇷 Testando API de TTS para Hebraico e Grego\n")
    
    # 1. Verificar se API está rodando
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            health = response.json()
            print(f"✅ API está rodando!")
            print(f"📱 Device: {health['device']}")
            print(f"🤖 Modelos carregados: {health['loaded_models']}")
            print(f"🌍 Idiomas: {health['supported_languages']}")
        else:
            print("❌ API não está respondendo")
            return False
    except:
        print("❌ Erro: API não está rodando")
        print("Execute: python -m uvicorn app.multi_model_api:app --host 0.0.0.0 --port 3000")
        return False
    
    # 2. Listar modelos disponíveis
    print("\n📋 Modelos disponíveis:")
    try:
        response = requests.get(f"{base_url}/models")
        models_data = response.json()
        for key, config in models_data["models"].items():
            print(f"  🔹 {key}: {config['name']}")
            langs = list(config['supported_languages'].keys())
            print(f"    📝 Idiomas: {', '.join(langs)}")
    except Exception as e:
        print(f"Erro ao listar modelos: {e}")
    
    # 3. Testes de geração de áudio
    test_cases = [
        {
            "name": "Hebraico - Saudação",
            "data": {
                "text": "שלום עולם, איך אתה היום?",
                "lang": "heb"
            },
            "filename": "hebrew_greeting.mp3"
        },
        {
            "name": "Hebraico - Números",
            "data": {
                "text": "אחד, שניים, שלושה, ארבעה, חמישה",
                "lang": "heb"
            },
            "filename": "hebrew_numbers.mp3"
        },
        {
            "name": "Grego - Saudação",
            "data": {
                "text": "Γεια σας, πώς είστε σήμερα;",
                "lang": "ell"
            },
            "filename": "greek_greeting.mp3"
        },
        {
            "name": "Grego - Alfabeto",
            "data": {
                "text": "Άλφα, Βήτα, Γάμμα, Δέλτα, Έψιλον",
                "lang": "ell"
            },
            "filename": "greek_alphabet.mp3"
        },
        {
            "name": "Hebraico - Texto religioso",
            "data": {
                "text": "ברוך השם לעולם ועד",
                "lang": "heb"
            },
            "filename": "hebrew_blessing.mp3"
        },
        {
            "name": "Grego - Filosofia",
            "data": {
                "text": "Γνώθι σεαυτόν",
                "lang": "ell"
            },
            "filename": "greek_philosophy.mp3"
        }
    ]
    
    print("\n🎵 Testando geração de áudio:")
    successful_tests = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   Texto: {test_case['data']['text']}")
        
        try:
            start_time = time.time()
            response = requests.post(f"{base_url}/speak", data=test_case['data'])
            end_time = time.time()
            
            if response.status_code == 200:
                # Salvar arquivo de áudio
                with open(test_case['filename'], 'wb') as f:
                    f.write(response.content)
                
                # Informações do cabeçalho
                model_used = response.headers.get('X-Model-Used', 'Unknown')
                language = response.headers.get('X-Language', 'Unknown')
                
                print(f"   ✅ Sucesso! ({end_time - start_time:.2f}s)")
                print(f"   🤖 Modelo: {model_used}")
                print(f"   🌍 Idioma: {language}")
                print(f"   💾 Salvo como: {test_case['filename']}")
                
                successful_tests += 1
                
            else:
                print(f"   ❌ Erro: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   📝 Detalhes: {json.dumps(error_detail, indent=6, ensure_ascii=False)}")
                except:
                    print(f"   📝 Resposta: {response.text}")
                    
        except Exception as e:
            print(f"   ❌ Exceção: {e}")
    
    # 4. Resumo
    print(f"\n📊 Resumo dos testes:")
    print(f"   ✅ Sucessos: {successful_tests}/{len(test_cases)}")
    print(f"   📁 Arquivos gerados: {[tc['filename'] for tc in test_cases[:successful_tests]]}")
    
    if successful_tests == len(test_cases):
        print("\n🎉 Todos os testes passaram! A API está funcionando perfeitamente.")
    elif successful_tests > 0:
        print(f"\n⚠️  {successful_tests} de {len(test_cases)} testes passaram.")
    else:
        print("\n❌ Nenhum teste passou. Verifique a configuração da API.")
    
    return successful_tests == len(test_cases)

def test_error_cases():
    """Testa casos de erro esperados"""
    base_url = "http://localhost:3000"
    
    print("\n🧪 Testando casos de erro:")
    
    error_cases = [
        {
            "name": "Idioma não suportado (inglês)",
            "data": {"text": "Hello world", "lang": "eng"},
            "expected_status": 400
        },
        {
            "name": "Texto vazio",
            "data": {"text": "", "lang": "heb"},
            "expected_status": 400
        },
        {
            "name": "Idioma inválido",
            "data": {"text": "שלום", "lang": "invalid"},
            "expected_status": 400
        },
        {
            "name": "Parâmetro obrigatório faltando (lang)",
            "data": {"text": "שלום"},
            "expected_status": 422
        }
    ]
    
    for i, test_case in enumerate(error_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        try:
            response = requests.post(f"{base_url}/speak", data=test_case['data'])
            
            if response.status_code == test_case['expected_status']:
                print(f"   ✅ Erro esperado capturado corretamente: {response.status_code}")
                try:
                    error_detail = response.json()
                    if 'detail' in error_detail:
                        print(f"   📝 Detalhes: {error_detail['detail']}")
                except:
                    pass
            else:
                print(f"   ⚠️  Status inesperado: {response.status_code} (esperado: {test_case['expected_status']})")
                
        except Exception as e:
            print(f"   ❌ Exceção: {e}")

def show_usage_examples():
    """Mostra exemplos de uso da API"""
    print("\n📚 Exemplos de uso:")
    
    examples = [
        {
            "language": "Hebraico",
            "flag": "🇮🇱",
            "curl": """curl -X POST "http://localhost:3000/speak" \\
     -H "Content-Type: application/x-www-form-urlencoded" \\
     -d "text=שלום עולם&lang=heb" \\
     --output hebrew.mp3""",
            "python": """import requests
response = requests.post('http://localhost:3000/speak', 
    data={'text': 'שלום עולם', 'lang': 'heb'})
with open('hebrew.mp3', 'wb') as f:
    f.write(response.content)"""
        },
        {
            "language": "Grego",
            "flag": "🇬🇷", 
            "curl": """curl -X POST "http://localhost:3000/speak" \\
     -H "Content-Type: application/x-www-form-urlencoded" \\
     -d "text=Γεια σας&lang=ell" \\
     --output greek.mp3""",
            "python": """import requests
response = requests.post('http://localhost:3000/speak',
    data={'text': 'Γεια σας', 'lang': 'ell'})
with open('greek.mp3', 'wb') as f:
    f.write(response.content)"""
        }
    ]
    
    for example in examples:
        print(f"\n{example['flag']} {example['language']}:")
        print("   CURL:")
        print(f"   {example['curl']}")
        print("\n   Python:")
        print(f"   {example['python']}")

if __name__ == "__main__":
    print("🔬 Teste de TTS para Hebraico e Grego\n")
    print("Este script testa:")
    print("• ✅ API funcionando")  
    print("• 📋 Modelos MMS-TTS")
    print("• 🇮🇱 Geração de áudio em Hebraico") 
    print("• 🇬🇷 Geração de áudio em Grego")
    print("• ⚠️  Tratamento de erros")
    print("=" * 50)
    
    # Executar testes principais
    success = test_hebrew_greek_api()
    
    # Executar testes de erro
    test_error_cases()
    
    # Mostrar exemplos de uso
    show_usage_examples()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Todos os testes principais passaram!")
        print("\n💡 Próximos passos:")
        print("• Ouça os arquivos MP3 gerados para verificar qualidade")
        print("• Use a API para seus textos em hebraico e grego")
        print("• Integre ao seu projeto")
    else:
        print("⚠️  Alguns testes falharam. Verifique os logs acima.")
        
    print("\n📚 Documentação da API: http://localhost:3000/docs")
    print("🏠 Homepage da API: http://localhost:3000/")
