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

def adreca_de(nom, defecte):
    """
    Una adreça que ve de l'entorn, amb el valor per defecte de debò.

    Una variable BUIDA ha de valer com si no hi fos. GitHub la posa igualment
    encara que no s'hagi definit al repositori, i llavors arriba una cadena
    buida: `os.environ.get(nom, defecte)` no fa servir el defecte, l'adreça
    queda en «/api/build/cataleg» i peta amb un error que no diu res del que
    passa de debò.
    """
    valor = (os.environ.get(nom) or "").strip().rstrip("/")
    if not valor:
        return defecte
    if not re.match(r"^https?://", valor, re.I):
        sys.exit(f"{nom} ha de començar per https:// i ara hi diu {valor!r}")
    return valor


# L'adreça de l'ERP: la que truca aquest programa i la que s'escriu a les
# pàgines perquè el navegador del visitant refresqui els preus. És la mateixa
# perquè les dues portes viuen al mateix nom, cadascuna al seu camí:
#   api.mtic.cat/api/public/*  el navegador de qualsevol
#   api.mtic.cat/api/build/*   només aquest programa, amb la clau
API = adreca_de("MTIC_API", "https://api.mtic.cat")
TOKEN = os.environ.get("MTIC_TOKEN", "")
TEMPS_ESPERA = 60
MIDA_MAXIMA_FOTO = 6 * 1024 * 1024

# Les menes d'imatge que es publiquen, i com s'anomena el fitxer de cadascuna
EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

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


def json_ld(dades):
    r"""
    Les dades estructurades, dins d'un <script> i sense poder-ne sortir.

    `json.dumps` no escapa els «<», i el navegador tanca un <script> en veure
    «</script>» encara que sigui dins d'una cadena. Un article que es digués
    «Tòner </script><script>…» injectaria el que volgués a la pàgina. Amb els
    tres caràcters escapats en \uXXXX el JSON continua sent el mateix i ja no
    hi ha manera de sortir-ne.
    """
    brut = json.dumps(dades, ensure_ascii=False, indent=1)
    return brut.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def euros(valor):
    """1234.5 -> 1.234,50 €, a l'espanyola."""
    sencer, decimals = f"{float(valor):.2f}".split(".")
    milers = re.sub(r"(?<=\d)(?=(\d{3})+$)", ".", sencer)
    return f"{milers},{decimals} €"


def capcaleres():
    """
    Les capçaleres de cada crida.

    L'agent d'usuari és de debò i no el de Python a seques: pel camí hi ha
    Cloudflare, i un «Python-urllib/3.12» que ve d'un centre de dades té tots
    els números de semblar un robot i que el parin abans d'arribar.

    Si algun dia hi ha Cloudflare Access davant de la porta de generació, el
    seu testimoni de servei va a les dues capçaleres de sota. Si no n'hi ha,
    no s'envien i no molesten.
    """
    capsaleres = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
        "User-Agent": "mtic-web/1.0 (+https://mtic.cat)",
    }
    access_id = os.environ.get("CF_ACCESS_CLIENT_ID", "").strip()
    access_secret = os.environ.get("CF_ACCESS_CLIENT_SECRET", "").strip()
    if access_id and access_secret:
        capsaleres["CF-Access-Client-Id"] = access_id
        capsaleres["CF-Access-Client-Secret"] = access_secret
    return capsaleres


def explica_error(e, ruta):
    """
    Qui ha dit que no, i per què.

    Importa distingir-ho: els codis de l'ERP són 401 (la clau no val) i 503
    (no n'hi ha cap de configurada). Qualsevol altra cosa ve de Cloudflare, i
    llavors la petició no ha arribat ni a casa. Dir-ho malament fa buscar on
    no toca, que és el que passava abans.
    """
    de_cloudflare = bool(e.headers.get("cf-ray") or e.headers.get("cf-mitigated"))
    qui = "Cloudflare" if de_cloudflare else "L'ERP"
    pistes = {
        401: "la clau de generació no és bona (WEB_BUILD_TOKEN i MTIC_TOKEN han de ser iguals)",
        403: "una regla de seguretat ha parat la petició abans d'arribar a l'ERP. "
             "Mira Security > Events al tauler de Cloudflare: hi dirà quina. "
             "Sol ser el Bot Fight Mode, la Browser Integrity Check o Access.",
        404: "aquesta adreça no la publica el túnel. Comprova el camí de la ruta de api.mtic.cat.",
        503: "l'ERP no té cap clau de generació configurada (WEB_BUILD_TOKEN al .env)",
    }
    ray = e.headers.get("cf-ray")
    return "\n".join(filter(None, [
        f"{qui} ha contestat {e.code} a {ruta}",
        f"  · {pistes[e.code]}" if e.code in pistes else None,
        f"  · Ray ID {ray}" if ray else None,
    ]))


def demana(ruta):
    """Una crida a l'ERP amb la clau de generació."""
    if not TOKEN:
        sys.exit("Falta MTIC_TOKEN: sense clau, l'ERP no dona el catàleg.")
    peticio = urllib.request.Request(f"{API}{ruta}", headers=capcaleres())
    try:
        with urllib.request.urlopen(peticio, timeout=TEMPS_ESPERA) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(explica_error(e, ruta))
    except OSError as e:
        sys.exit(f"No s'ha pogut parlar amb l'ERP ({e})")


RE_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,98}[a-z0-9])?$")


def slug_segur(slug):
    """
    L'adreça decideix el NOM DEL FITXER que s'escriu, i ve de la xarxa.

    L'ERP només en fa de lletres, xifres i guions, però aquí no ens ho podem
    creure sense mirar-ho: un «../../index» escriuria a sobre d'una pàgina del
    lloc, i un amb cometes se sortiria de l'atribut href. El que no encaixi es
    deixa estar i es diu per pantalla.
    """
    return bool(slug) and bool(RE_SLUG.match(str(slug)))


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
    """
    Només http(s). `urllib` també sap obrir file:// i ftp://, i l'adreça surt
    d'un fitxer que escriu el majorista: amb un file:///etc/passwd per imatge,
    això llegiria un fitxer del servidor i el desaria en un repositori públic
    fent veure que és una foto.
    """
    if not url or not (url.startswith("/") or re.match(r"^https?://", url, re.I)):
        return None

    # Si ja la tenim amb qualsevol extensió, no es torna a demanar
    for provada in EXTENSIONS.values():
        if os.path.exists(os.path.join(FOTOS, nom + provada)):
            return f"/media/botiga/{nom}{provada}"

    if url.startswith("/"):
        # Una adreça d'aquest ERP: la foto la serveix ell, darrere la clau
        peticio = urllib.request.Request(f"{API}{url}", headers=capcaleres())
    else:
        peticio = urllib.request.Request(url, headers={"User-Agent": "mtic-web/1.0"})

    try:
        with urllib.request.urlopen(peticio, timeout=TEMPS_ESPERA) as resposta:
            dades = resposta.read(MIDA_MAXIMA_FOTO + 1)
            tipus = (resposta.headers.get("content-type") or "").split(";")[0].strip().lower()
    except (OSError, urllib.error.HTTPError):
        return None          # una foto que falla no atura la generació
    if not dades or len(dades) > MIDA_MAXIMA_FOTO:
        return None

    """
    L'extensió surt del que diu el servidor i, si no ho diu, de l'adreça.

    Les fotos que serveix l'ERP vénen per una adreça sense extensió
    (/api/build/foto/12): mirant només l'adreça, un PNG acabava desat com a
    .jpg. El navegador ho aguanta, però el fitxer mentiria sobre què és.
    """
    extensio = EXTENSIONS.get(tipus)
    if not extensio:
        del_url = os.path.splitext(url.split("?")[0])[1].lower()
        extensio = del_url if del_url in EXTENSIONS.values() else ".jpg"

    os.makedirs(FOTOS, exist_ok=True)
    with open(os.path.join(FOTOS, nom + extensio), "wb") as f:
        f.write(dades)
    return f"/media/botiga/{nom}{extensio}"


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
    <meta name="mtic-api" content="{API}">

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

    extra = ('    <script type="application/ld+json">\n' + json_ld(schema) + "\n    </script>\n")
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
                f'<span>{esc(c["count"])}</span></button>' for c in cataleg["categories"]]

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

    extra = ('    <script type="application/ld+json">\n' + json_ld(schema) + "\n    </script>\n")
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

    # El que tingui una adreça rara no es dibuixa: vegeu slug_segur()
    for nom, llista, clau in (("producte", cataleg["products"], "slug"),
                              ("article", articles["posts"], "slug")):
        dolents = [x for x in llista if not slug_segur(x.get(clau))]
        for x in dolents:
            print(f"  ! {nom} amb adreça no vàlida, no es publica: {x.get(clau)!r}")
            llista.remove(x)

    # Les fotos, un cop: la mateixa serveix per a les dues llengües
    fotos_per_ref = {}
    for producte in cataleg["products"]:
        arrel = re.sub(r"[^a-z0-9]+", "-", producte["ref"].lower()).strip("-")
        baixades = []
        for n, origen in enumerate(producte.get("images") or [], start=1):
            # Compte amb el nom: `local` ja vol dir «sense xarxa» aquí dins
            copia = baixa_foto(origen, arrel if n == 1 else f"{arrel}-{n}")
            if copia:
                baixades.append(copia)
        fotos_per_ref[producte["ref"]] = baixades

        """
        Les adreces d'origen es canvien per les còpies nostres ABANS de desar
        el json.

        Aquest repositori és PÚBLIC, i les adreces solen ser de casa del
        majorista: desant-les aquí, el que no volem que surti a l'HTML acabaria
        igualment publicat, i a més amb historial. Un cop les fotos són
        baixades, d'on venien ja no fa cap falta.
        """
        producte["images"] = baixades

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
