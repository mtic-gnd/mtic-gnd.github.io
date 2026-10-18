#!/usr/bin/env python3
"""
mtic · eina de manteniment de la web estàtica.

Què fa (sense dependències, només Python 3):
  1. Regenera a TOTES les pàgines les parts comunes: capçalera, peu,
     bloc comú del <head> (favicons, tipografia, estils, scripts) i
     les etiquetes hreflang entre català i castellà.
  2. Regenera sitemap.xml amb les pàgines indexables, els seus hreflang
     i un lastmod real (data de l'últim commit de cada fitxer, o avui
     si el fitxer té canvis sense desar a git).

Ús, des de l'arrel del repositori:
    python3 eines/web.py

Quan afegeixis una pàgina nova:
  - crea el fitxer HTML (pots copiar-ne una de semblant),
  - afegeix-la a PAGINES aquí sota (amb la seva parella en l'altre idioma),
  - executa l'eina i fes commit.

Si canvies styles.css o main.js, puja VERSIO perquè els navegadors
descarreguin la versió nova.
"""
import datetime
import os
import re
import subprocess
import sys

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMINI = "https://mtic.cat"
VERSIO = "2026101803"
MAPS = "https://www.google.com/maps?cid=5369165064477127583"
INSTAGRAM = "https://www.instagram.com/mtic.gandesa/"
TEL = "+34711550872"
TEL_VISIBLE = "711 55 08 72"
WA = "https://wa.me/34711550872"
CORREU = "info@mtic.cat"

# (url català, url castellà, secció del menú, indexable)
PARELLES = [
    ("/", "/es/", "inici", True),
    ("/serveis.html", "/es/servicios.html", "serveis", True),
    ("/reparacio-ordinadors.html", "/es/reparacion-ordenadores.html", "serveis", True),
    ("/recuperacio-dades.html", "/es/recuperacion-datos.html", "serveis", True),
    ("/venda-ordinadors.html", "/es/venta-ordenadores.html", "serveis", True),
    ("/manteniment-informatic.html", "/es/mantenimiento-informatico.html", "serveis", True),
    ("/xarxes-wifi.html", "/es/redes-wifi.html", "serveis", True),
    ("/pagines-web.html", "/es/paginas-web.html", "serveis", True),
    ("/sobre-nosaltres.html", "/es/sobre-nosotros.html", "sobre", True),
    ("/contacte.html", "/es/contacto.html", "contacte", True),
    ("/avis-legal.html", "/es/aviso-legal.html", None, False),
    ("/privacitat.html", "/es/privacidad.html", None, False),
    ("/cookies.html", "/es/cookies.html", None, False),
    ("/termes.html", "/es/terminos.html", None, False),
]
# Pàgines sense parella
SOLES = [("/404.html", "ca", None)]

ICONA_TEL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/></svg>'
ICONA_MENU = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="28" height="28" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>'

TXT = {
    "ca": {
        "inici": ("/", "Inici"), "serveis": ("/serveis.html", "Serveis"),
        "sobre": ("/sobre-nosaltres.html", "Sobre nosaltres"), "contacte": ("/contacte.html", "Contacte"),
        "altre_idioma": ("es", "Castellano"), "marca_aria": "mtic, anar a l'inici",
        "obre_menu": "Obre el menú", "nav_aria": "Navegació principal",
        "descripcio": "Reparació i venda d'ordinadors, manteniment informàtic i desenvolupament web a Gandesa i tota la Terra Alta.",
        "contacte_t": "Contacte", "horari": "Dilluns a divendres, 9:00–19:00",
        "taller": "Taller a Gandesa, amb cita prèvia",
        "serveis_t": "Serveis",
        "serveis_llista": [
            ("/reparacio-ordinadors.html", "Reparació d'ordinadors"),
            ("/recuperacio-dades.html", "Recuperació de dades"),
            ("/venda-ordinadors.html", "Venda d'ordinadors"),
            ("/manteniment-informatic.html", "Manteniment informàtic"),
            ("/xarxes-wifi.html", "Xarxes i WiFi"),
            ("/pagines-web.html", "Pàgines web"),
        ],
        "fitxa": "Fitxa de Google", "drets": "mtic, Serveis Informàtics i Digitals. Gandesa, Tarragona.",
        "legal": [("/avis-legal.html", "Avís legal"), ("/privacitat.html", "Privacitat"),
                  ("/cookies.html", "Galetes"), ("/termes.html", "Termes i condicions")],
        "config_cookies": "Configura les galetes",
    },
    "es": {
        "inici": ("/es/", "Inicio"), "serveis": ("/es/servicios.html", "Servicios"),
        "sobre": ("/es/sobre-nosotros.html", "Sobre nosotros"), "contacte": ("/es/contacto.html", "Contacto"),
        "altre_idioma": ("ca", "Català"), "marca_aria": "mtic, ir al inicio",
        "obre_menu": "Abrir el menú", "nav_aria": "Navegación principal",
        "descripcio": "Reparación y venta de ordenadores, mantenimiento informático y desarrollo web en Gandesa y toda la Terra Alta.",
        "contacte_t": "Contacto", "horari": "Lunes a viernes, 9:00–19:00",
        "taller": "Taller en Gandesa, con cita previa",
        "serveis_t": "Servicios",
        "serveis_llista": [
            ("/es/reparacion-ordenadores.html", "Reparación de ordenadores"),
            ("/es/recuperacion-datos.html", "Recuperación de datos"),
            ("/es/venta-ordenadores.html", "Venta de ordenadores"),
            ("/es/mantenimiento-informatico.html", "Mantenimiento informático"),
            ("/es/redes-wifi.html", "Redes y WiFi"),
            ("/es/paginas-web.html", "Páginas web"),
        ],
        "fitxa": "Ficha de Google", "drets": "mtic, Serveis Informàtics i Digitals. Gandesa, Tarragona.",
        "legal": [("/es/aviso-legal.html", "Aviso legal"), ("/es/privacidad.html", "Privacidad"),
                  ("/es/cookies.html", "Cookies"), ("/es/terminos.html", "Términos y condiciones")],
        "config_cookies": "Configurar cookies",
    },
}


def fitxer(url):
    """URL pública -> camí del fitxer al repositori."""
    if url.endswith("/"):
        return os.path.join(ARREL, url.lstrip("/"), "index.html")
    return os.path.join(ARREL, url.lstrip("/"))


def capcalera(idioma, seccio, url_altre):
    t = TXT[idioma]
    enllacos = []
    for clau in ("inici", "serveis", "sobre", "contacte"):
        href, nom = t[clau]
        actual = ' aria-current="page"' if clau == seccio else ""
        enllacos.append(f'                <a href="{href}"{actual}>{nom}</a>')
    codi, nom_idioma = t["altre_idioma"]
    enllacos.append(f'                <a class="idioma" href="{url_altre}" hreflang="{codi}" lang="{codi}">{nom_idioma}</a>')
    enllacos.append(f'                <a class="boto" href="tel:{TEL}">{ICONA_TEL} {TEL_VISIBLE}</a>')
    inici = t["inici"][0]
    return (
        '<header class="capcalera">\n'
        '        <div class="container">\n'
        f'            <a class="marca" href="{inici}" aria-label="{t["marca_aria"]}">\n'
        '                <picture>\n'
        '                    <source srcset="/media/images/logo-mtic.webp" type="image/webp">\n'
        '                    <img src="/media/images/logo-mtic-96.png" alt="mtic Serveis Informàtics i Digitals" width="282" height="40">\n'
        '                </picture>\n'
        '            </a>\n'
        f'            <button class="menu-obre" aria-expanded="false" aria-controls="menu" aria-label="{t["obre_menu"]}">{ICONA_MENU}</button>\n'
        f'            <nav id="menu" class="menu" aria-label="{t["nav_aria"]}">\n'
        + "\n".join(enllacos) + "\n"
        '            </nav>\n'
        '        </div>\n'
        '    </header>'
    )


def peu(idioma):
    t = TXT[idioma]
    serveis = "\n".join(f'                    <li><a href="{h}">{n}</a></li>' for h, n in t["serveis_llista"])
    legal = "\n".join(f'                <a href="{h}">{n}</a>' for h, n in t["legal"])
    return (
        '<footer class="peu">\n'
        '        <div class="container">\n'
        '            <div>\n'
        '                <p class="logo-peu">MTIC</p>\n'
        f'                <p>{t["descripcio"]}</p>\n'
        '            </div>\n'
        '            <div>\n'
        f'                <h2>{t["contacte_t"]}</h2>\n'
        '                <ul>\n'
        f'                    <li><a href="tel:{TEL}">{TEL_VISIBLE}</a></li>\n'
        f'                    <li><a href="{WA}" target="_blank" rel="noopener">WhatsApp</a></li>\n'
        f'                    <li><a href="mailto:{CORREU}">{CORREU}</a></li>\n'
        f'                    <li>{t["horari"]}</li>\n'
        f'                    <li>{t["taller"]}</li>\n'
        '                </ul>\n'
        '            </div>\n'
        '            <div>\n'
        f'                <h2>{t["serveis_t"]}</h2>\n'
        '                <ul>\n'
        f'{serveis}\n'
        '                </ul>\n'
        '            </div>\n'
        '            <div>\n'
        '                <h2>mtic</h2>\n'
        '                <ul>\n'
        f'                    <li><a href="{t["sobre"][0]}">{t["sobre"][1]}</a></li>\n'
        f'                    <li><a href="{t["contacte"][0]}">{t["contacte"][1]}</a></li>\n'
        f'                    <li><a href="{MAPS}" target="_blank" rel="noopener">{t["fitxa"]}</a></li>\n'
        f'                    <li><a href="{INSTAGRAM}" target="_blank" rel="noopener">Instagram</a></li>\n'
        '                </ul>\n'
        '            </div>\n'
        '            <div class="legal">\n'
        f'                <span>© <span data-any>2026</span> {t["drets"]}</span>\n'
        f'{legal}\n'
        f'                <button type="button" data-obre-cookies>{t["config_cookies"]}</button>\n'
        '            </div>\n'
        '        </div>\n'
        '    </footer>'
    )


def bloc_comu():
    return (
        "<!-- comú:inici · generat per eines/web.py, no l'editis a mà -->\n"
        f'    <link rel="icon" href="/media/favicon/favicon.ico?v=20260918" sizes="any">\n'
        f'    <link rel="icon" type="image/png" href="/media/favicon/favicon-96x96.png?v=20260918" sizes="96x96">\n'
        f'    <link rel="apple-touch-icon" href="/media/favicon/apple-touch-icon.png?v=20260918">\n'
        f'    <link rel="manifest" href="/media/favicon/site.webmanifest?v=20260918">\n'
        '    <meta name="apple-mobile-web-app-title" content="mtic">\n'
        '    <link rel="preload" href="/media/fonts/archivo-latin.woff2" as="font" type="font/woff2" crossorigin>\n'
        f'    <link rel="stylesheet" href="/media/styles/styles.css?v={VERSIO}">\n'
        f'    <script src="/media/js/main.js?v={VERSIO}" defer></script>\n'
        "    <!-- comú:fi -->"
    )


def bloc_idiomes(url_ca, url_es):
    return (
        "<!-- idiomes:inici -->\n"
        f'    <link rel="alternate" hreflang="ca" href="{DOMINI}{url_ca}">\n'
        f'    <link rel="alternate" hreflang="es" href="{DOMINI}{url_es}">\n'
        f'    <link rel="alternate" hreflang="x-default" href="{DOMINI}{url_ca}">\n'
        "    <!-- idiomes:fi -->"
    )


RE_GTAG = re.compile(r'\s*<script async src="https://www\.googletagmanager\.com/gtag/js\?id=[^"]+"></script>\s*<script>.*?</script>', re.S)
RE_COMU_VELL = re.compile(r'<link rel="icon".*?<script src="/media/js/main\.js[^"]*" defer></script>', re.S)
RE_COMU = re.compile(r"<!-- comú:inici.*?<!-- comú:fi -->", re.S)
RE_IDIOMES = re.compile(r"<!-- idiomes:inici -->.*?<!-- idiomes:fi -->", re.S)
RE_HREFLANG_VELL = re.compile(r'\n\s*<link rel="alternate" hreflang="[^"]+" href="[^"]+">')
RE_CANONICAL = re.compile(r'(<link rel="canonical" href="[^"]+">)')
RE_CAPCALERA = re.compile(r'<header class="capcalera">.*?</header>', re.S)
RE_PEU = re.compile(r'<footer class="peu">.*?</footer>', re.S)


def actualitza(cami, idioma, seccio, url_altre, parella):
    with open(cami, encoding="utf-8") as f:
        html = f.read()
    original = html

    html = RE_GTAG.sub("", html, count=1)
    # Fonts de Google: ara s'allotgen a /media/fonts
    html = re.sub(r'\s*<link rel="preconnect" href="https://fonts\.(googleapis|gstatic)\.com"[^>]*>', "", html)
    html = re.sub(r'\s*<link rel="stylesheet" href="https://fonts\.googleapis\.com/[^"]*">', "", html)

    if RE_COMU.search(html):
        html = RE_COMU.sub(lambda m: bloc_comu(), html, count=1)
    elif RE_COMU_VELL.search(html):
        html = RE_COMU_VELL.sub(lambda m: bloc_comu(), html, count=1)
    else:
        sys.exit(f"No trobo on posar el bloc comú a {cami}")

    if parella:
        bloc = bloc_idiomes(*parella)
        if RE_IDIOMES.search(html):
            html = RE_IDIOMES.sub(lambda m: bloc, html, count=1)
        else:
            html = RE_HREFLANG_VELL.sub("", html)
            html = RE_CANONICAL.sub(lambda m: m.group(1) + "\n    " + bloc, html, count=1)

    if not RE_CAPCALERA.search(html) or not RE_PEU.search(html):
        sys.exit(f"Falta la capçalera o el peu a {cami}")
    html = RE_CAPCALERA.sub(lambda m: capcalera(idioma, seccio, url_altre), html, count=1)
    html = RE_PEU.sub(lambda m: peu(idioma), html, count=1)

    if html != original:
        with open(cami, "w", encoding="utf-8") as f:
            f.write(html)
        return True
    return False


def data_modificacio(cami):
    rel = os.path.relpath(cami, ARREL)
    avui = datetime.date.today().isoformat()
    try:
        brut = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ARREL, capture_output=True, text=True).stdout
        if brut.strip():
            return avui
        data = subprocess.run(["git", "log", "-1", "--format=%cs", "--", rel], cwd=ARREL, capture_output=True, text=True).stdout.strip()
        return data or avui
    except OSError:
        return avui


def sitemap():
    linies = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for idx in (0, 1):
        for ca, es, _seccio, indexable in PARELLES:
            if not indexable:
                continue
            url = (ca, es)[idx]
            linies += ["  <url>",
                       f"    <loc>{DOMINI}{url}</loc>",
                       f"    <lastmod>{data_modificacio(fitxer(url))}</lastmod>",
                       f'    <xhtml:link rel="alternate" hreflang="ca" href="{DOMINI}{ca}"/>',
                       f'    <xhtml:link rel="alternate" hreflang="es" href="{DOMINI}{es}"/>',
                       f'    <xhtml:link rel="alternate" hreflang="x-default" href="{DOMINI}{ca}"/>',
                       "  </url>"]
    linies.append("</urlset>")
    with open(os.path.join(ARREL, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(linies) + "\n")


def main():
    canvis = []
    for ca, es, seccio, _indexable in PARELLES:
        for idioma, url, altre in (("ca", ca, es), ("es", es, ca)):
            cami = fitxer(url)
            if not os.path.exists(cami):
                sys.exit(f"Falta el fitxer {cami} (és a PARELLES)")
            if actualitza(cami, idioma, seccio, altre, (ca, es)):
                canvis.append(os.path.relpath(cami, ARREL))
    for url, idioma, seccio in SOLES:
        cami = fitxer(url)
        altre = "/es/" if idioma == "ca" else "/"
        if actualitza(cami, idioma, seccio, altre, None):
            canvis.append(os.path.relpath(cami, ARREL))
    sitemap()
    print(f"{len(canvis)} pàgines actualitzades; sitemap.xml regenerat.")
    for c in canvis:
        print("  ·", c)


if __name__ == "__main__":
    main()
