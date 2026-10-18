#!/usr/bin/env python3
"""
mtic · generador de la botiga i dels articles.

Va a buscar a l'ERP què hi ha publicat i n'escriu pàgines HTML de debò. No és
cap canvi de model: la web segueix sent estàtica i a GitHub Pages, i aquestes
pàgines són fitxers com els altres, amb la mateixa capçalera, el mateix peu i
els mateixos hreflang, que surten de `eines/web.py`.

Per què pàgines i no javascript que demani les dades en obrir-les:

  - Google indexa fitxers. Una fitxa que només existeix si corre el javascript
    val molt menys, i aquest lloc té molta feina feta d'SEO per llençar-la.
  - Si cau la llum a casa, o el túnel, la botiga segueix sent-hi. El preu que
    es veu és el de l'última generació; el javascript només el REFRESCA si
    l'ERP contesta, i si no contesta no es nota res.

Les fotos es BAIXEN i es serveixen des de mtic.cat. Enllaçar-les a casa del
majorista explicaria a qualsevol que miri el codi amb qui treballo, i es
trencarien el dia que ells canviïn l'adreça.

Ús:
    MTIC_API=https://api.mtic.cat MTIC_TOKEN=... python3 eines/genera.py
    python3 eines/genera.py --local        (reaprofita dades/*.json, sense xarxa)
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import markdown  # noqa: E402
import web  # noqa: E402

ARREL = web.ARREL
DOMINI = web.DOMINI
DADES = os.path.join(ARREL, "dades")
FOTOS = os.path.join(ARREL, "media", "botiga")

API = os.environ.get("MTIC_API", "https://api.mtic.cat").rstrip("/")
# L'adreça que escriurà la pàgina per refrescar els preus. És una altra variable
# perquè generant des de GitHub es pot haver d'entrar per una porta i el
# visitant per una altra.
API_PUBLICA = os.environ.get("MTIC_API_PUBLICA", "https://api.mtic.cat").rstrip("/")
TOKEN = os.environ.get("MTIC_TOKEN", "")
TEMPS_ESPERA = 60
MIDA_MAXIMA_FOTO = 6 * 1024 * 1024

# Les seccions noves, en els dos idiomes.
RUTES = {
    "botiga": {"ca": "/botiga/", "es": "/es/tienda/"},
    "articles": {"ca": "/articles/", "es": "/es/articulos/"},
}

T = {
    "ca": {
        "botiga_titol": "Botiga · ordinadors, tòners i accessoris a Gandesa",
        "botiga_descripcio": "Preus d'ordinadors, portàtils, tòners, tintes, cables i accessoris. "
                             "Demana'ls directament i te'ls preparo.",
        "botiga_entrada": "Aquests són els preus que tinc ara mateix. No hi ha carret: "
                          "digue'm què necessites i t'ho preparo, amb la garantia i el muntatge inclosos.",
        "articles_titol": "Articles · consells d'informàtica",
        "articles_descripcio": "Consells, avaries explicades i coses que val la pena saber abans de "
                               "comprar o reparar un ordinador.",
        "articles_entrada": "El que vaig aprenent al taller, explicat sense embuts.",
        "demana": "Demana'l per WhatsApp",
        "contacta": "Escriu-me",
        "preu_iva": "IVA inclòs",
        "preu_sense": "sense IVA",
        "consulta": "Consulta'm el preu",
        "tenim": "A la botiga",
        "demanar": "Te'l porto en 24-48 h",
        "preguntar": "Pregunta'm disponibilitat",
        "ref": "Referència",
        "orientatiu": "Preus orientatius, revisats el {data}. Confirma'm disponibilitat abans de comprar.",
        "cap": "Encara no hi ha res publicat.",
        "tornar": "Tornar a la botiga",
        "tornar_articles": "Tots els articles",
        "inici": "Inici",
        "llegir": "Llegir",
        "wa_text": "Hola! M'interessa {nom} ({ref})",
        "categoria_tot": "Tot",
    },
    "es": {
        "botiga_titol": "Tienda · ordenadores, tóners y accesorios en Gandesa",
        "botiga_descripcio": "Precios de ordenadores, portátiles, tóners, tintas, cables y accesorios. "
                             "Pídemelos directamente y te los preparo.",
        "botiga_entrada": "Estos son los precios que tengo ahora mismo. No hay carrito: "
                          "dime qué necesitas y te lo preparo, con la garantía y el montaje incluidos.",
        "articles_titol": "Artículos · consejos de informática",
        "articles_descripcio": "Consejos, averías explicadas y cosas que vale la pena saber antes de "
                               "comprar o reparar un ordenador.",
        "articles_entrada": "Lo que voy aprendiendo en el taller, explicado sin rodeos.",
        "demana": "Pídelo por WhatsApp",
        "contacta": "Escríbeme",
        "preu_iva": "IVA incluido",
        "preu_sense": "sin IVA",
        "consulta": "Consúltame el precio",
        "tenim": "En la tienda",
        "demanar": "Te lo traigo en 24-48 h",
        "preguntar": "Pregúntame disponibilidad",
        "ref": "Referencia",
        "orientatiu": "Precios orientativos, revisados el {data}. Confírmame disponibilidad antes de comprar.",
        "cap": "Todavía no hay nada publicado.",
        "tornar": "Volver a la tienda",
        "tornar_articles": "Todos los artículos",
        "inici": "Inicio",
        "llegir": "Leer",
        "wa_text": "¡Hola! Me interesa {nom} ({ref})",
        "categoria_tot": "Todo",
    },
}

ESTAT = {
    "in_stock": "tenim",
    "on_order": "demanar",
    "unknown": "preguntar",
}


# ------------------------------------------------------------- utilitats

def esc(valor):
    return html.escape("" if valor is None else str(valor), quote=True)


def euros(valor):
    """1234.5 -> 1.234,50 €, a l'espanyola."""
    sencer, decimals = f"{float(valor):.2f}".split(".")
    milers = re.sub(r"(?<=\d)(?=(\d{3})+$)", ".", sencer)
    return f"{milers},{decimals} €"


def demana(ruta):
    """Una crida a l'ERP amb la clau de generació."""
    if not TOKEN:
        sys.exit("Falta MTIC_TOKEN: sense clau, l'ERP no dona el catàleg.")
    peticio = urllib.request.Request(
        f"{API}{ruta}",
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(peticio, timeout=TEMPS_ESPERA) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"L'ERP ha contestat {e.code} a {ruta}"
                 + (" · la clau no és bona" if e.code == 401 else ""))
    except OSError as e:
        sys.exit(f"No s'ha pogut parlar amb l'ERP ({e})")


def desa_json(nom, dades):
    os.makedirs(DADES, exist_ok=True)
    with open(os.path.join(DADES, nom), "w", encoding="utf-8") as f:
        json.dump(dades, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def llegeix_json(nom):
    cami = os.path.join(DADES, nom)
    if not os.path.exists(cami):
        sys.exit(f"No hi ha {cami}: la primera vegada cal generar-ho amb l'ERP, no amb --local.")
    with open(cami, encoding="utf-8") as f:
        return json.load(f)


def escriu(url, html_text):
    """Escriu la pàgina i diu si ha canviat."""
    cami = web.fitxer(url)
    os.makedirs(os.path.dirname(cami), exist_ok=True)
    if os.path.exists(cami):
        with open(cami, encoding="utf-8") as f:
            if f.read() == html_text:
                return False
    with open(cami, "w", encoding="utf-8") as f:
        f.write(html_text)
    return True


# ----------------------------------------------------------------- fotos

def baixa_foto(url, nom):
    """
    Es baixa una foto del majorista i la desa a /media/botiga.

    Si ja la tenim, no es torna a demanar: el manual d'Infortisa demana
    justament això, no repetir descàrregues del que ja s'ha baixat.
    """
    if not url:
        return None
    extensio = os.path.splitext(url.split("?")[0])[1].lower()
    if extensio not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        extensio = ".jpg"
    desti = os.path.join(FOTOS, nom + extensio)
    public = f"/media/botiga/{nom}{extensio}"

    if os.path.exists(desti):
        return public

    os.makedirs(FOTOS, exist_ok=True)
    peticio = urllib.request.Request(url, headers={"User-Agent": "mtic-web/1.0"})
    # Si la foto porta la clau de l'ERP a dins és perquè ve de la seva porta
    if url.startswith("/"):
        peticio = urllib.request.Request(f"{API}{url}", headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(peticio, timeout=TEMPS_ESPERA) as resposta:
            dades = resposta.read(MIDA_MAXIMA_FOTO + 1)
    except (OSError, urllib.error.HTTPError):
        return None          # una foto que falla no atura la generació
    if not dades or len(dades) > MIDA_MAXIMA_FOTO:
        return None

    with open(desti, "wb") as f:
        f.write(dades)
    return public


# ----------------------------------------------------------------- pàgina

def pagina(idioma, url, url_altre, titol, descripcio, cos, seccio="serveis",
           imatge=None, dades_extra="", classe=""):
    """
    El motlle de totes les pàgines que genera aquest programa.

    La capçalera, el peu i el bloc comú del <head> surten de `eines/web.py`:
    són els mateixos que a la resta del lloc i es mantenen en un sol lloc.
    """
    alternatiu = f'{DOMINI}{imatge}' if imatge and imatge.startswith("/") else (imatge or f"{DOMINI}/media/images/og-mtic.jpg")
    # Sense pàgina equivalent no s'hi posa cap hreflang: apuntar a l'índex de
    # l'altre idioma seria dir que és el mateix contingut, i no ho és.
    idiomes = (web.bloc_idiomes(url if idioma == "ca" else url_altre,
                                url_altre if idioma == "ca" else url)
               if url_altre else "")
    return f"""<!DOCTYPE html>
<html lang="{idioma}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{esc(titol)}</title>
    <meta name="description" content="{esc(descripcio)}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{DOMINI}{url}">
    {idiomes}
    <meta name="theme-color" content="#5e17eb">
    <meta name="mtic-api" content="{API_PUBLICA}">

    <meta property="og:type" content="website">
    <meta property="og:url" content="{DOMINI}{url}">
    <meta property="og:title" content="{esc(titol)}">
    <meta property="og:description" content="{esc(descripcio)}">
    <meta property="og:image" content="{esc(alternatiu)}">
    <meta property="og:locale" content="{'ca_ES' if idioma == 'ca' else 'es_ES'}">
    <meta property="og:site_name" content="mtic">
    <meta name="twitter:card" content="summary_large_image">

    {web.bloc_comu()}
    <script src="/media/js/botiga.js?v={web.VERSIO}" defer></script>
{dades_extra}</head>
<body{f' class="{classe}"' if classe else ''}>
    <a class="salta" href="#contingut">{'Salta al contingut' if idioma == 'ca' else 'Saltar al contenido'}</a>
    {web.capcalera(idioma, seccio, url_altre)}

    <main id="contingut">
{cos}
    </main>

    {web.peu(idioma)}
</body>
</html>
"""


# ----------------------------------------------------------------- botiga

def fitxa_producte(idioma, producte, categories, fotos):
    t = T[idioma]
    altre = "es" if idioma == "ca" else "ca"
    url = f"{RUTES['botiga'][idioma]}{producte['slug']}.html"
    url_altre = f"{RUTES['botiga'][altre]}{producte['slug']}.html"
    categoria = categories.get(producte.get("category")) or {}
    preu = producte["price_with_vat"]
    estat = t[ESTAT.get(producte.get("availability"), "preguntar")]

    galeria = ""
    if fotos:
        mines = "".join(
            f'<button type="button" class="mini" data-foto="{esc(f)}">'
            f'<img src="{esc(f)}" alt="" loading="lazy" width="64" height="64"></button>'
            for f in fotos[1:6])
        galeria = (
            '<figure class="foto-producte">\n'
            f'                <img id="foto-gran" src="{esc(fotos[0])}" alt="{esc(producte["name"])}" loading="eager">\n'
            + (f'                <div class="mines">{mines}</div>\n' if mines else "")
            + "            </figure>"
        )

    wa = esc("https://wa.me/34711550872?text=" + urllib.parse.quote(
        t["wa_text"].format(nom=producte["name"], ref=producte["ref"])))
    contacte = "/contacte.html" if idioma == "ca" else "/es/contacto.html"

    cos_md = markdown.a_html(producte.get("body") or "") if producte.get("body") else ""
    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": producte["name"],
        "sku": producte["ref"],
        "description": producte.get("summary") or producte.get("body") or producte["name"],
        "brand": {"@type": "Brand", "name": producte["brand"]} if producte.get("brand") else None,
        "image": [f"{DOMINI}{f}" for f in fotos] or None,
        "offers": {
            "@type": "Offer",
            "url": f"{DOMINI}{url}",
            "priceCurrency": "EUR",
            "price": f"{preu:.2f}",
            "availability": "https://schema.org/InStock" if producte.get("availability") == "in_stock"
                            else "https://schema.org/PreOrder",
            "seller": {"@type": "LocalBusiness", "name": "mtic"},
        },
    }
    schema = {k: v for k, v in schema.items() if v is not None}

    cos = f"""        <section class="seccio">
        <div class="container">
            <nav class="molles" aria-label="{'Molles de pa' if idioma == 'ca' else 'Migas de pan'}">
                <a href="{'/' if idioma == 'ca' else '/es/'}">{t['inici']}</a><span>·</span>
                <a href="{RUTES['botiga'][idioma]}">{'Botiga' if idioma == 'ca' else 'Tienda'}</a>
                {f'<span>·</span><span>{esc(categoria.get("name", ""))}</span>' if categoria else ''}
            </nav>

            <div class="producte">
            {galeria}
                <div class="producte-dades">
                    <h1>{esc(producte['name'])}</h1>
                    {f'<p class="entradeta">{esc(producte["summary"])}</p>' if producte.get('summary') else ''}
                    <p class="preu" data-preu-ref="{esc(producte['ref'])}">
                        <strong data-preu>{euros(preu)}</strong>
                        <span class="preu-nota">{t['preu_iva']} · <span data-preu-sense>{euros(producte['price'])}</span> {t['preu_sense']}</span>
                    </p>
                    <p class="estat" data-estat-ref="{esc(producte['ref'])}"
                       data-in_stock="{esc(t['tenim'])}" data-on_order="{esc(t['demanar'])}"
                       data-unknown="{esc(t['preguntar'])}">{esc(estat)}</p>
                    <p class="botons">
                        <a class="boto" href="{wa}" target="_blank" rel="noopener">{t['demana']}</a>
                        <a class="boto-linia" href="{contacte}">{t['contacta']}</a>
                    </p>
                    <p class="ref-petita">{t['ref']}: <code>{esc(producte['ref'])}</code></p>
                </div>
            </div>

            {f'<div class="text-llarg descripcio-producte">{cos_md}</div>' if cos_md else ''}

            <p class="actualitzat">{t['orientatiu'].format(data=datetime.date.today().strftime('%d/%m/%Y'))}</p>
            <p><a href="{RUTES['botiga'][idioma]}">← {t['tornar']}</a></p>
        </div>
    </section>"""

    extra = ('    <script type="application/ld+json">\n'
             + json.dumps(schema, ensure_ascii=False, indent=1) + "\n    </script>\n")
    return url, pagina(idioma, url, url_altre,
                       f"{producte['name']} · mtic",
                       producte.get("summary") or f"{producte['name']}. {t['botiga_descripcio']}",
                       cos, seccio="botiga", imatge=fotos[0] if fotos else None, dades_extra=extra)


def targeta(idioma, producte, fotos, amb_enllac):
    t = T[idioma]
    url = f"{RUTES['botiga'][idioma]}{producte['slug']}.html"
    foto = fotos[0] if fotos else None
    nom = esc(producte["name"])
    preu = (f'<span class="preu" data-preu-ref="{esc(producte["ref"])}">'
            f'<strong data-preu>{euros(producte["price_with_vat"])}</strong></span>')
    imatge = (f'<img src="{esc(foto)}" alt="{nom}" loading="lazy">' if foto
              else '<span class="sense-foto" aria-hidden="true"></span>')

    if amb_enllac:
        return (f'<a class="article-botiga" href="{url}" data-categoria="{esc(producte.get("category") or "")}">'
                f'{imatge}<span class="nom">{nom}</span>{preu}</a>')
    # Les famílies que no mereixen fitxa pròpia: només la fila, amb el seu botó
    wa = esc("https://wa.me/34711550872?text=" + urllib.parse.quote(
        t["wa_text"].format(nom=producte["name"], ref=producte["ref"])))
    return (f'<div class="article-botiga fila" data-categoria="{esc(producte.get("category") or "")}">'
            f'{imatge}<span class="nom">{nom}</span>{preu}'
            f'<a class="boto-linia" href="{wa}" target="_blank" rel="noopener">{t["demana"]}</a></div>')


def index_botiga(idioma, cataleg, fotos_per_ref):
    t = T[idioma]
    url = RUTES["botiga"][idioma]
    url_altre = RUTES["botiga"]["es" if idioma == "ca" else "ca"]
    categories = {c["slug"]: c for c in cataleg["categories"]}

    filtres = [f'<button type="button" class="filtre actiu" data-filtra="">{t["categoria_tot"]}</button>']
    filtres += [f'<button type="button" class="filtre" data-filtra="{esc(c["slug"])}">{esc(c["name"])} '
                f'<span>{c["count"]}</span></button>' for c in cataleg["categories"]]

    # Dues llistes i no una: les famílies que no mereixen fitxa pròpia són
    # files amples, i barrejades amb les targetes quedaven estretes i amb el
    # botó sortint per fora de la caixa.
    fitxes, files = [], []
    for producte in cataleg["products"]:
        amb_fitxa = (categories.get(producte.get("category")) or {}).get("layout", "page") == "page"
        (fitxes if amb_fitxa else files).append(
            targeta(idioma, producte, fotos_per_ref.get(producte["ref"], []), amb_fitxa))

    graella = "\n                ".join(fitxes)
    llistat = "\n                ".join(files)
    if not fitxes and not files:
        graella = f'<p>{t["cap"]}</p>'

    cos = f"""        <section class="cap-pagina">
        <div class="container">
            <h1>{'Botiga' if idioma == 'ca' else 'Tienda'}</h1>
            <p>{t['botiga_entrada']}</p>
        </div>
    </section>

    <section class="seccio">
        <div class="container">
            <div class="filtres">
                {"".join(filtres)}
            </div>
            <div class="graella-botiga">
                {graella}
            </div>
            {f'<div class="files-botiga">{llistat}</div>' if llistat else ''}
            <p class="actualitzat">{t['orientatiu'].format(data=datetime.date.today().strftime('%d/%m/%Y'))}</p>
        </div>
    </section>"""

    return url, pagina(idioma, url, url_altre, f"{t['botiga_titol']} | mtic",
                       t["botiga_descripcio"], cos, seccio="botiga")


# --------------------------------------------------------------- articles

def fitxa_article(idioma, post):
    t = T[idioma]
    url = f"{RUTES['articles'][idioma]}{post['slug']}.html"
    altre_idioma = "es" if idioma == "ca" else "ca"
    url_altre = (f"{RUTES['articles'][altre_idioma]}{post['translation']['slug']}.html"
                 if post.get("translation") else None)

    cos_html = markdown.a_html(post.get("body_md") or "")
    resum = post.get("summary") or markdown.nomes_text(post.get("body_md") or "", 160)
    data = (post.get("published_at") or "")[:10]

    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post["title"],
        "description": resum,
        "datePublished": data,
        "dateModified": (post.get("updated_at") or data)[:10],
        "inLanguage": idioma,
        "mainEntityOfPage": f"{DOMINI}{url}",
        "author": {"@type": "Organization", "name": "mtic"},
        "publisher": {"@type": "Organization", "name": "mtic"},
    }
    if post.get("cover_image"):
        schema["image"] = post["cover_image"]

    portada = (f'<figure class="portada-article"><img src="{esc(post["cover_image"])}" '
               f'alt="{esc(post["title"])}" loading="eager"></figure>'
               if post.get("cover_image") else "")

    cos = f"""        <section class="cap-pagina">
        <div class="container">
            <nav class="molles" aria-label="{'Molles de pa' if idioma == 'ca' else 'Migas de pan'}">
                <a href="{'/' if idioma == 'ca' else '/es/'}">{t['inici']}</a><span>·</span>
                <a href="{RUTES['articles'][idioma]}">{'Articles' if idioma == 'ca' else 'Artículos'}</a>
            </nav>
            <h1>{esc(post['title'])}</h1>
            <p class="data-article"><time datetime="{esc(data)}">{esc(data)}</time></p>
        </div>
    </section>

    <section class="seccio">
        <div class="container">
            {portada}
            <article class="text-llarg">
{cos_html}
            </article>
            <p><a href="{RUTES['articles'][idioma]}">← {t['tornar_articles']}</a></p>
        </div>
    </section>"""

    extra = ('    <script type="application/ld+json">\n'
             + json.dumps(schema, ensure_ascii=False, indent=1) + "\n    </script>\n")
    return url, pagina(idioma, url, url_altre, f"{post['title']} · mtic", resum, cos,
                       seccio="articles", imatge=post.get("cover_image"), dades_extra=extra)


def index_articles(idioma, posts):
    t = T[idioma]
    url = RUTES["articles"][idioma]
    url_altre = RUTES["articles"]["es" if idioma == "ca" else "ca"]

    fitxes = []
    for post in posts:
        resum = post.get("summary") or markdown.nomes_text(post.get("body_md") or "", 140)
        data = (post.get("published_at") or "")[:10]
        fitxes.append(
            f'<a class="fitxa-article" href="{RUTES["articles"][idioma]}{post["slug"]}.html">'
            f'<span class="data"><time datetime="{esc(data)}">{esc(data)}</time></span>'
            f'<h2>{esc(post["title"])}</h2><p>{esc(resum)}</p>'
            f'<span class="llegir">{t["llegir"]} →</span></a>')

    llista = "\n                ".join(fitxes) if fitxes else f'<p>{t["cap"]}</p>'

    cos = f"""        <section class="cap-pagina">
        <div class="container">
            <h1>{'Articles' if idioma == 'ca' else 'Artículos'}</h1>
            <p>{t['articles_entrada']}</p>
        </div>
    </section>

    <section class="seccio">
        <div class="container">
            <div class="llista-articles">
                {llista}
            </div>
        </div>
    </section>"""

    return url, pagina(idioma, url, url_altre, f"{t['articles_titol']} | mtic",
                       t["articles_descripcio"], cos, seccio="articles")


# ------------------------------------------------------------------ main

def main():
    local = "--local" in sys.argv

    if local:
        cataleg, articles = llegeix_json("botiga.json"), llegeix_json("articles.json")
    else:
        cataleg, articles = demana("/api/build/cataleg"), demana("/api/build/articles")

    # Les fotos, un cop: la mateixa serveix per a les dues llengües
    fotos_per_ref = {}
    for producte in cataleg["products"]:
        nom_foto = re.sub(r"[^a-z0-9]+", "-", producte["ref"].lower()).strip("-")
        baixada = baixa_foto(producte.get("image_source"), nom_foto)
        fotos_per_ref[producte["ref"]] = [baixada] if baixada else []

        """
        L'adreça d'origen es canvia per la còpia nostra ABANS de desar el json.

        Aquest repositori és PÚBLIC, i `image_source` és sovint una adreça del
        majorista: desant-la aquí, el que no volem que surti a l'HTML acabaria
        igualment publicat, i a més amb historial. Un cop la foto és baixada ja
        no la necessitem per a res.
        """
        producte["image_source"] = baixada

    if not local:
        desa_json("botiga.json", cataleg)
        desa_json("articles.json", articles)

    canvis = []
    pagines = []          # per al sitemap: (url_ca, url_es)

    for idioma in ("ca", "es"):
        url, text = index_botiga(idioma, cataleg, fotos_per_ref)
        if escriu(url, text):
            canvis.append(url)
        url, text = index_articles(idioma, [p for p in articles["posts"] if p["lang"] == idioma])
        if escriu(url, text):
            canvis.append(url)

    pagines.append((RUTES["botiga"]["ca"], RUTES["botiga"]["es"]))
    pagines.append((RUTES["articles"]["ca"], RUTES["articles"]["es"]))

    categories = {c["slug"]: c for c in cataleg["categories"]}
    for producte in cataleg["products"]:
        if (categories.get(producte.get("category")) or {}).get("layout", "page") != "page":
            continue          # els que només són una fila del llistat no tenen fitxa
        urls = {}
        for idioma in ("ca", "es"):
            url, text = fitxa_producte(idioma, producte, categories, fotos_per_ref.get(producte["ref"], []))
            urls[idioma] = url
            if escriu(url, text):
                canvis.append(url)
        pagines.append((urls["ca"], urls["es"]))

    for post in articles["posts"]:
        url, text = fitxa_article(post["lang"], post)
        if escriu(url, text):
            canvis.append(url)
        parella = post.get("translation")
        if post["lang"] == "ca":
            altre = f"{RUTES['articles']['es']}{parella['slug']}.html" if parella else None
            pagines.append((url, altre))
        elif not parella:
            # Un article només en castellà també ha de sortir al sitemap
            pagines.append((None, url))

    # El sitemap el fa web.py: aquí només se li diu quines pàgines hi ha més
    desa_json("pagines.json", [{"ca": ca, "es": es} for ca, es in pagines])
    web.main()

    print(f"{len(canvis)} pàgines generades o canviades.")
    for c in canvis[:40]:
        print("  ·", c)
    if len(canvis) > 40:
        print(f"  … i {len(canvis) - 40} més")


if __name__ == "__main__":
    main()
