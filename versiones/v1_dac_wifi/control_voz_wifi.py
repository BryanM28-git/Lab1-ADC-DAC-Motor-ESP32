import requests
import re
import sounddevice as sd
from scipy.io.wavfile import write
import speech_recognition as sr
import os

# --- API Y CONEXIÓN ---
API_KEY = 'TU_API_KEY_AQUI'
API_URL = 'https://api.deepseek.com/v1/chat/completions'
IP_ESP32 = '192.168.x.x'  # Reemplaza con la IP del ESP32

def enviar_mensaje(mensaje, modelo='deepseek-chat'):
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }

    instruccion_sistema = (
        "Eres un controlador de un motor DC. El usuario te dará instrucciones por voz en lenguaje natural. "
        "Debes interpretar a qué velocidad quiere ir y responder ÚNICAMENTE con un número entero "
        "entre 0 (apagado) y 255 (velocidad máxima). Si dice 'mitad', responde 127. "
        "No agregues texto, puntos ni explicaciones, solo el número."
    )

    data = {
        'model': modelo,
        'messages': [
            {'role': 'system', 'content': instruccion_sistema},
            {'role': 'user', 'content': mensaje}
        ]
    }

    try:
        response = requests.post(API_URL, headers=headers, json=data)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Error Inesperado: {e}"

def enviar_a_esp32(valor_dac):
    try:
        url = f"http://{IP_ESP32}/?vel={valor_dac}"
        respuesta = requests.get(url, timeout=2)
        return respuesta.text
    except Exception as e:
        return f"Error de conexión con ESP32: {e}"

def escuchar_microfono_alternativo():
    """Graba audio con sounddevice y lo procesa con SpeechRecognition"""
    fs = 44100  # Frecuencia de muestreo
    segundos = 4  # Tiempo de grabación (ajusta si necesitas más tiempo para hablar)
    archivo_temp = "instruccion_temp.wav"
    
    print("\n🟢 Habla ahora... (grabando por 4 segundos)")
    
    # Grabamos el audio
    grabacion = sd.rec(int(segundos * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()  # Esperamos a que termine de grabar
    print("⏳ Procesando audio...")
    
    # Guardamos el archivo temporalmente
    write(archivo_temp, fs, grabacion)
    
    # Lo pasamos a SpeechRecognition
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(archivo_temp) as source:
            audio_data = recognizer.record(source)
            texto = recognizer.recognize_google(audio_data, language='es-CO')
            print(f"Tú dijiste: {texto}")
            return texto
    except sr.UnknownValueError:
        print("⚠️ No se entendió el audio, intenta hablar más claro.")
        return None
    except Exception as e:
        print(f"❌ Error al procesar audio: {e}")
        return None
    finally:
        # Limpiamos el archivo temporal para no ocupar espacio
        if os.path.exists(archivo_temp):
            os.remove(archivo_temp)

def main():
    print("==================================================")
    print("🎙️ Control por voz del motor con DeepSeek 🎙️")
    print("==================================================")

    while True:
        input("\nPresiona ENTER para empezar a grabar (o presiona Ctrl+C para salir)...")
        
        mensaje_usuario = escuchar_microfono_alternativo()

        if not mensaje_usuario:
            continue

        if 'salir' in mensaje_usuario.lower() or 'apagar' in mensaje_usuario.lower():
            # Por seguridad, si decimos salir, mandamos un 0 al motor antes de cerrar
            print("Chatbot: Apagando motor y cerrando sistema. ¡Hasta Luego!")
            enviar_a_esp32(0)
            break 

        respuesta_ia = enviar_mensaje(mensaje_usuario)
        numeros = re.findall(r'\d+', respuesta_ia)
        
        if numeros:
            valor_dac = int(numeros[0])
            valor_dac = max(0, min(255, valor_dac))
            
            print(f"Chatbot: Entendido. Ajustando voltaje (DAC: {valor_dac})...")
            
            rpm_actual = enviar_a_esp32(valor_dac)
            print(f"ESP32 Reporta -> Velocidad actual: {rpm_actual} RPM")
        else:
            print(f"Chatbot: No pude extraer la velocidad. Respuesta original: {respuesta_ia}")

if __name__ == "__main__":
    main()