import os
import re
import time
import requests
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import filedialog, scrolledtext

TIMEOUT = 30
DELAY = 1.0

# URLs del sitio
LOGIN_PAGE_URL = "https://www.poringa.net/login"
LOGIN_URL = "https://www.poringa.net/"

HEADERS_COMUNES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
}

# Nombres que Windows no permite usar como nombre de archivo/carpeta
RESERVADOS = {"CON", "PRN", "AUX", "NUL",
              *(f"COM{i}" for i in range(1, 10)),
              *(f"LPT{i}" for i in range(1, 10))}

# Sesión compartida: la que se autentica es la que se usa para descargar
session = requests.Session()
sesion_ok = False


# =========================
# UTILIDADES
# =========================
def limpiar_nombre(texto):
    texto = texto.strip()
    texto = re.sub(r'[\\/:*?"<>|]', '', texto)
    texto = re.sub(r'[\x00-\x1f]', '', texto)
    texto = re.sub(r'\s+', ' ', texto)
    texto = texto[:150]
    texto = texto.rstrip(" .")
    if texto.upper() in RESERVADOS:
        texto = "_" + texto
    return texto


def obtener_nombre(html):
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        nombre = limpiar_nombre(h1.get_text())
        if nombre:
            return nombre
    if soup.title and soup.title.string:
        nombre = limpiar_nombre(soup.title.string)
        if nombre:
            return nombre
    return None


def log(msg):
    log_box.insert(tk.END, msg + "\n")
    log_box.see(tk.END)
    root.update()


# =========================
# SEMÁFORO DE LOGIN
# =========================
def set_estado(estado, texto):
    """estado: 'gris' | 'rojo' | 'verde'"""
    colores = {"gris": "#b0b0b0", "rojo": "#d62828", "verde": "#2ecc40"}
    luz.itemconfig(circulo, fill=colores[estado])
    lbl_estado.config(text=texto)


def mostrar_ejecutar(mostrar):
    if mostrar:
        btn_ejecutar.pack(pady=10, before=log_box)
    else:
        btn_ejecutar.pack_forget()


def invalidar_login(event=None):
    """Si el usuario cambia usuario/contraseña, hay que volver a validar."""
    global sesion_ok, session
    if sesion_ok:
        sesion_ok = False
        session = requests.Session()
        set_estado("gris", "Sin verificar")
        mostrar_ejecutar(False)


# =========================
# LOGIN
# =========================
def sesion_activa(sess):
    """
    Verifica que realmente estemos logueados: al pedir la página de login,
    si el sitio todavía muestra el formulario con el campo de contraseña,
    la sesión NO está iniciada. Ajusta si el sitio se comporta distinto.
    """
    try:
        r = sess.get(LOGIN_PAGE_URL, headers=HEADERS_COMUNES, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        log(f"❌ Error verificando sesión: {e}")
        return False

    soup = BeautifulSoup(r.text, "html.parser")
    hay_form_login = soup.find("input", {"name": "pass"}) is not None
    return not hay_form_login


def hacer_login(sess, usuario, password):
    try:
        r0 = sess.get(LOGIN_PAGE_URL, headers=HEADERS_COMUNES, timeout=TIMEOUT)
        r0.raise_for_status()
    except Exception as e:
        log(f"❌ Error al cargar la página de login: {e}")
        return False

    payload = {
        "nick": usuario,
        "pass": password,
        "connect": "",
        "redirect": "/",
    }
    headers = {
        **HEADERS_COMUNES,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.poringa.net",
        "Referer": LOGIN_PAGE_URL,
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        r = sess.post(LOGIN_URL, data=payload, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        log(f"❌ Error al hacer login: {e}")
        return False

    if not sess.cookies.get_dict():
        log("⚠️ No se recibieron cookies de sesión.")
        return False

    if "login" in r.url.lower() and "usuario o contraseña" in r.text.lower():
        log("❌ Usuario o contraseña inválidos.")
        return False

    # Confirmación final: ¿el sitio nos reconoce como logueados?
    if not sesion_activa(sess):
        log("❌ El sitio sigue mostrando el formulario de login.")
        return False

    return True


def probar_login():
    global session, sesion_ok
    usuario = entry_user.get().strip()
    password = entry_pass.get().strip()

    if not usuario or not password:
        set_estado("rojo", "Ingresa usuario y contraseña")
        return

    session = requests.Session()
    sesion_ok = False
    mostrar_ejecutar(False)
    set_estado("gris", "Conectando...")
    btn_login.config(state="disabled")
    root.update()

    log("🔐 Iniciando sesión...")
    ok = hacer_login(session, usuario, password)
    btn_login.config(state="normal")

    if ok:
        sesion_ok = True
        set_estado("verde", "Login correcto")
        log(f"✅ Login correcto. Cookies: {list(session.cookies.get_dict().keys())}")
        mostrar_ejecutar(True)
    else:
        set_estado("rojo", "Login fallido")
        log("🛑 No se pudo iniciar sesión.")


# =========================
# PROCESAMIENTO
# =========================
def ejecutar():
    if not sesion_ok:
        log("❌ Primero debes iniciar sesión correctamente.")
        return

    carpeta_txt = entry_txt.get()
    carpeta_salida = entry_out.get()

    if not os.path.isdir(carpeta_txt):
        log("❌ Carpeta TXT inválida")
        return
    if not carpeta_salida:
        log("❌ Carpeta destino vacía")
        return
    os.makedirs(carpeta_salida, exist_ok=True)

    archivos = [f for f in os.listdir(carpeta_txt) if f.endswith(".txt")]

    for archivo in archivos:
        ruta_txt = os.path.join(carpeta_txt, archivo)
        nombre_base = os.path.splitext(archivo)[0]
        carpeta_madre = os.path.join(carpeta_salida, nombre_base)
        os.makedirs(carpeta_madre, exist_ok=True)

        log(f"\n📂 Procesando archivo: {archivo}")

        try:
            with open(ruta_txt, "r", encoding="utf-8") as f:
                urls = [u.strip() for u in f if u.strip()]
        except Exception as e:
            log(f"❌ Error leyendo archivo: {e}")
            continue

        for i, url in enumerate(urls, 1):
            log(f"[{i}/{len(urls)}] {url}")
            try:
                r = session.get(url, timeout=TIMEOUT)
                r.raise_for_status()
                html = r.text
            except Exception as e:
                log(f"❌ Error: {e}")
                continue

            if "login" in r.url.lower():
                log("⚠️ Posible sesión expirada o redirección a login detectada")
                set_estado("rojo", "Sesión expirada")

            nombre = obtener_nombre(html) or f"pagina_{i}"

            carpeta_final = os.path.join(carpeta_madre, nombre)
            if os.path.exists(carpeta_final):
                carpeta_final = f"{carpeta_final}_{i}"

            try:
                os.makedirs(carpeta_final, exist_ok=True)
                with open(os.path.join(carpeta_final, "source.html"), "w", encoding="utf-8") as f:
                    f.write(html)
            except Exception as e:
                log(f"❌ Error guardando '{nombre}': {e}")
                continue

            log(f"✅ Guardado en: {os.path.basename(carpeta_final)}")
            time.sleep(DELAY)

    log("\n🏁 TERMINADO")


# =========================
# UI
# =========================
def elegir_carpeta(entry):
    ruta = filedialog.askdirectory()
    if ruta:
        entry.delete(0, tk.END)
        entry.insert(0, ruta)


root = tk.Tk()
root.title("Scraper HTML por lotes (con login)")
root.geometry("700x640")

frame = tk.Frame(root)
frame.pack(pady=10)

# Input TXT
tk.Label(frame, text="Carpeta de archivos TXT:").grid(row=0, column=0, sticky="w")
entry_txt = tk.Entry(frame, width=60)
entry_txt.grid(row=1, column=0)
tk.Button(frame, text="Seleccionar", command=lambda: elegir_carpeta(entry_txt)).grid(row=1, column=1)

# Input Output
tk.Label(frame, text="Carpeta destino:").grid(row=2, column=0, sticky="w")
entry_out = tk.Entry(frame, width=60)
entry_out.grid(row=3, column=0)
tk.Button(frame, text="Seleccionar", command=lambda: elegir_carpeta(entry_out)).grid(row=3, column=1)

# Usuario / contraseña
tk.Label(frame, text="Usuario:").grid(row=4, column=0, sticky="w", pady=(10, 0))
entry_user = tk.Entry(frame, width=40)
entry_user.grid(row=5, column=0, sticky="w")

tk.Label(frame, text="Contraseña:").grid(row=6, column=0, sticky="w", pady=(10, 0))
entry_pass = tk.Entry(frame, width=40, show="*")
entry_pass.grid(row=7, column=0, sticky="w")

# Si cambian credenciales, se invalida el login anterior
entry_user.bind("<Key>", invalidar_login)
entry_pass.bind("<Key>", invalidar_login)

# Botón de login + semáforo
fila_login = tk.Frame(frame)
fila_login.grid(row=8, column=0, columnspan=2, sticky="w", pady=(12, 0))

btn_login = tk.Button(fila_login, text="🔑 Iniciar sesión", command=probar_login, height=1)
btn_login.pack(side="left")

luz = tk.Canvas(fila_login, width=26, height=26, highlightthickness=0)
luz.pack(side="left", padx=(12, 4))
circulo = luz.create_oval(3, 3, 23, 23, fill="#b0b0b0", outline="#555555")

lbl_estado = tk.Label(fila_login, text="Sin verificar")
lbl_estado.pack(side="left")

# Botón ejecutar (oculto hasta que el login sea correcto)
btn_ejecutar = tk.Button(root, text="▶ Ejecutar", command=ejecutar, height=2, bg="green", fg="white")

# Logs
log_box = scrolledtext.ScrolledText(root, width=85, height=20)
log_box.pack(pady=10)

root.mainloop()