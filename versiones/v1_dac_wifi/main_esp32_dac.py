import network
import socket
from machine import Pin, Timer, DAC
import time

# --- 1. Configuración WiFi ---
# REEMPLAZA CON EL NOMBRE Y CLAVE DE TU RED (Debe ser la misma red a la que está conectada tu PC)
ssid = "TU_RED_WIFI"
password = "TU_CONTRASEÑA"

station = network.WLAN(network.STA_IF)
station.active(True)
station.connect(ssid, password)

print("Conectando a WiFi...")
while not station.isconnected():
    time.sleep(0.5)
    
ip_esp32 = station.ifconfig()[0]
print("=========================================")
print(f"¡Conectado! La IP del ESP32 es: {ip_esp32}")
print("-> Copia esta IP en la variable IP_ESP32 de tu Visual Studio Code <-")
print("=========================================")

# --- 2. Configuración Hardware (DAC y Encoder) ---
# DAC en el GPIO 25 (Envía el voltaje al Enable del L298N)
dac = DAC(Pin(25))

# Encoder en el GPIO 34 (Lee la rueda del motor)
encoder_pin = Pin(34, Pin.IN, Pin.PULL_UP)
pulse_count = 0
rpm = 0

def count_pulse(pin):
    global pulse_count
    pulse_count += 1

# Interrupción para contar cada pulso que marque la herradura
encoder_pin.irq(trigger=Pin.IRQ_RISING, handler=count_pulse)

def calculate_rpm(timer):
    global pulse_count, rpm
    # Tienes un encoder de 20 pulsos por vuelta
    # RPM = (Pulsos / 20) * 60 -> Que equivale a multiplicar por 3
    rpm = pulse_count * 3
    pulse_count = 0

# Se dispara exactamente cada 1 segundo (1000 ms)
timer = Timer(0)
timer.init(period=1000, mode=Timer.PERIODIC, callback=calculate_rpm)

# --- 3. Servidor Web No Bloqueante ---
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5)
s.setblocking(False) # Esto evita que el ESP32 se "congele" esperando el Wi-Fi

velocidad_deseada = 0

try:
    while True:
        try:
            # Espera instrucciones del PC
            conn, addr = s.accept()
            request = conn.recv(1024).decode('utf-8')
            
            # Buscar el valor numérico que manda Visual Studio (ej: GET /?vel=127)
            if '/?vel=' in request:
                inicio = request.find('/?vel=') + 6
                fin = request.find(' ', inicio)
                valor_str = request[inicio:fin]
                
                try:
                    velocidad_deseada = int(valor_str)
                    # Limitamos por seguridad de 0 a 255
                    velocidad_deseada = max(0, min(255, velocidad_deseada))
                    
                    # Escribimos el voltaje en el DAC
                    dac.write(velocidad_deseada)
                    print(f"Recibido por voz -> Ajustando DAC a: {velocidad_deseada}")
                except ValueError:
                    pass
            
            # Responde al PC devolviendo las RPM actuales
            response = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n{rpm}"
            conn.send(response)
            conn.close()
            
        except OSError:
            # Si no ha llegado nada por Wi-Fi, sigue su camino sin pausarse
            pass
            
        time.sleep(0.05)
        
except KeyboardInterrupt:
    timer.deinit()
    dac.write(0) # Apaga el motor al detener el código
    print("Programa detenido.")