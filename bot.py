#!/usr/bin/env python3
"""Bot de ofertas Black Friday: lee feeds de chollos de varias tiendas,
filtra por palabras clave y avisa por Telegram. Solo usa la librería estándar."""
import json, os, re, sys, time, html, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).parent
CONFIG = BASE / "config.json"
SEEN = BASE / "vistos.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) ofertas-bot/1.0"


def cargar_config():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cfg["telegram_token"] = os.environ.get("TELEGRAM_TOKEN", cfg.get("telegram_token", ""))
    cfg["telegram_chat_id"] = os.environ.get("TELEGRAM_CHAT_ID", cfg.get("telegram_chat_id", ""))
    return cfg


def descargar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def a_numero(txt):
    """'1.299,99€' / '$1,299.99' / '19.99' -> float"""
    if not txt:
        return None
    t = re.sub(r"[^\d.,]", "", str(txt))
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        ent, _, dec = t.rpartition(",")
        t = f"{ent.replace(',', '')}.{dec}" if len(dec) <= 2 else t.replace(",", "")
    elif t.count(".") > 1 or re.search(r"\.\d{3}$", t):
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def parsear_feed(xml_bytes, tienda_feed):
    root = ET.fromstring(xml_bytes)
    ofertas = []
    for item in root.iter("item"):
        g = lambda tag: (item.findtext(tag) or "").strip()
        titulo, link = html.unescape(g("title")), g("link")
        desc = re.sub(r"<[^>]+>", " ", html.unescape(g("description")))
        precio, tienda, temp = None, None, None
        for el in item:  # campos extra tipo <pepper:merchant name=".." price=".."/>
            tag = el.tag.split("}")[-1].lower()
            if tag == "merchant":
                tienda = el.get("name") or tienda
                precio = a_numero(el.get("price")) or precio
            elif tag in ("temperature", "temp"):
                temp = a_numero(el.text)
        if precio is None:
            m = re.search(r"(\d[\d.,]*)\s?(?:€|EUR)|(?:\$|MXN\s?)\s?(\d[\d.,]*)", titulo)
            if m:
                precio = a_numero(m.group(1) or m.group(2))
        m = re.search(r"-?\s?(\d{1,2})\s?%", titulo + " " + desc)
        descuento = int(m.group(1)) if m else None
        categoria = " / ".join(c.text.strip() for c in item.findall("category") if c.text)
        ofertas.append({
            "id": g("guid") or link, "titulo": titulo, "link": link, "precio": precio,
            "descuento": descuento, "tienda": tienda or tienda_feed, "temperatura": temp, "categoria": categoria,
            "texto": f"{titulo} {desc}".lower(),
        })
    return ofertas


def coincide(o, busq):
    texto = o["texto"]
    cats = [c.lower() for c in busq.get("categorias", [])]
    if cats and not any(c in o.get("categoria", "").lower() for c in cats):
        return False
    palabras = busq.get("palabras", [])
    if palabras and not any(k.lower() in texto for k in palabras):
        return False
    if any(x.lower() in texto for x in busq.get("excluir", [])):
        return False
    if busq.get("precio_max") is not None and (o["precio"] is None or o["precio"] > busq["precio_max"]):
        return False
    if busq.get("descuento_min") and (o["descuento"] or 0) < busq["descuento_min"]:
        return False
    tiendas = [t.lower() for t in busq.get("tiendas", [])]
    if tiendas and not any(t in (o["tienda"] or "").lower() for t in tiendas):
        return False
    return True


def enviar_telegram(cfg, texto):
    if not cfg["telegram_token"] or not cfg["telegram_chat_id"]:
        print("[sin Telegram configurado]\n" + texto + "\n")
        return
    url = f"https://api.telegram.org/bot{cfg['telegram_token']}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": cfg["telegram_chat_id"], "text": texto,
                                   "parse_mode": "HTML", "disable_web_page_preview": "false"}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30).read()


def formatear(o, nombre_busq):
    partes = [f"🔥 <b>{html.escape(o['titulo'])}</b>"]
    info = []
    if o["precio"] is not None: info.append(f"💰 {o['precio']:g}")
    if o["descuento"]: info.append(f"📉 -{o['descuento']}%")
    if o["tienda"]: info.append(f"🏬 {html.escape(o['tienda'])}")
    if info: partes.append(" · ".join(info))
    partes.append(f"🔎 {html.escape(nombre_busq)}\n{o['link']}")
    return "\n".join(partes)


def ciclo(cfg, vistos, primera_vez):
    nuevas = 0
    for feed in cfg["feeds"]:
        try:
            ofertas = parsear_feed(descargar(feed["url"]), feed.get("nombre"))
        except Exception as e:
            print(f"Error leyendo {feed['url']}: {e}", file=sys.stderr)
            continue
        for o in ofertas:
            if o["id"] in vistos:
                continue
            vistos.add(o["id"])
            if primera_vez and cfg.get("ignorar_existentes_al_arrancar", False):
                continue
            for b in cfg["busquedas"]:
                if coincide(o, b):
                    enviar_telegram(cfg, formatear(o, b["nombre"]))
                    nuevas += 1
                    break
    return nuevas


def main():
    cfg = cargar_config()
    vistos = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    primera = not SEEN.exists()
    una_vez = "--una-vez" in sys.argv
    while True:
        n = ciclo(cfg, vistos, primera)
        primera = False
        SEEN.write_text(json.dumps(list(vistos)[-5000:]))
        print(time.strftime("%H:%M:%S"), f"{n} ofertas nuevas enviadas")
        if una_vez:
            break
        time.sleep(cfg.get("intervalo_minutos", 10) * 60)


if __name__ == "__main__":
    main()
