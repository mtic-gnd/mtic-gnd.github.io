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
        "destacat": "Destacat",
        "oferta": "Oferta",
        "afegir": "Afegeix",
        "cerca": "Busca un producte o una referència",
        "cap_resultat": "Cap producte amb aquest nom.",
        "nomes_ofertes": "Ofertes",
        "des_de": "des de",
        "variants": "Tria el model",
        "variant": "Model",
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
        "destacat": "Destacado",
        "oferta": "Oferta",
        "afegir": "Añadir",
        "cerca": "Busca un producto o una referencia",
        "cap_resultat": "Ningún producto con ese nombre.",
        "nomes_ofertes": "Ofertas",
        "des_de": "desde",
        "variants": "Elige el modelo",
        "variant": "Modelo",
    },
}

ESTRELLA = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" width="12" height="12">'
            '<path d="M12 2l3 6.5 7 .9-5 4.8 1.2 7L12 17.8 5.8 21.2 7 14.2 2 9.4l7-.9z"/></svg>')

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

    Si ja la tenim, no es torna a demanar: el manual del majorista demana
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

    """
    Una foto que ja és nostra no es torna a baixar.

    Les famílies ensenyen les fotos de les seves variants, i aquelles ja
    s'han baixat abans amb el nom de la referència. Sense això es tornaven a
    demanar amb un altre nom i quedaven desades dues vegades, i generant en
    local —on les adreces ja són les còpies— no es trobaven mai.
    """
    if url.startswith("/media/") and os.path.exists(os.path.join(ARREL, url.lstrip("/"))):
        return url

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
        # Totes les fotos tenen miniatura, també la primera: sense ella, un
        # cop en canviaves no hi havia manera de tornar a la d'entrada.
        mines = "" if len(fotos) < 2 else "".join(
            f'<button type="button" class="mini{" actiu" if n == 0 else ""}" data-foto="{esc(f)}">'
            f'<img src="{esc(f)}" alt="" loading="lazy" width="64" height="64"></button>'
            for n, f in enumerate(fotos[:6]))
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
                    {distintius(idioma, producte)}
                    <p class="preu" data-preu-ref="{esc(producte['ref'])}">
                        <strong data-preu>{euros(preu)}</strong>
                        {f'<s class="abans">{euros(producte["pvpr_with_vat"])}</s>' if producte.get('pvpr_with_vat') else ''}
                        <span class="preu-nota">{t['preu_iva']} · <span data-preu-sense>{euros(producte['price'])}</span> {t['preu_sense']}</span>
                    </p>
                    <p class="estat" data-estat-ref="{esc(producte['ref'])}"
                       data-in_stock="{esc(t['tenim'])}" data-on_order="{esc(t['demanar'])}"
                       data-unknown="{esc(t['preguntar'])}">{esc(estat)}</p>
                    <p class="botons">
                        <a class="boto" href="{wa}" target="_blank" rel="noopener">{t['demana']}</a>
                        {boto_afegir(idioma, producte)}
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


def etiqueta_variant(nom_familia, variant):
    """
    Com se'n diu la variant al desplegable.

    Si encara no se li ha posat etiqueta a l'ERP, hi arriba el nom sencer del
    producte: «Cartutx de tinta Epson 604 Cian» dins d'una pàgina que ja es
    diu «Cartutxos de tinta Epson 604». Traient-ne el que ja diu el títol en
    queda «Cian», que és l'única cosa que canvia i l'única que s'ha de llegir.
    """
    net = variant.strip()
    arrel = nom_familia.strip().rstrip("s").lower()
    if len(arrel) > 6 and net.lower().startswith(arrel):
        tallat = net[len(arrel):].lstrip(" ·-–—,")
        if tallat:
            return tallat
    return net


def fitxa_familia(idioma, familia, categories, fotos, fotos_per_ref):
    """
    La pàgina d'una família: una de sola, amb les variants a dins.

    Un cartutx de tinta no és un article, és sis: l'Epson 604 ve en negre,
    cian, magenta, groc i en dos multipacks. Sis fitxes que deien gairebé el
    mateix no són sis pàgines —per a qui mira és soroll i per a Google és
    contingut duplicat—, així que és una.

    Les variants van en un desplegable i no en una taula. Una taula de cinc
    files amb quatre columnes no cap en un mòbil i obliga a comparar-ho tot
    de cop; comprant no es compara, es tria el color que s'ha acabat. En
    triar-la canvien la foto, el preu, la disponibilitat i la referència:
    la pàgina ensenya una cosa i no cinc.
    """
    t = T[idioma]
    altre = "es" if idioma == "ca" else "ca"
    url = f"{RUTES['botiga'][idioma]}{familia['slug']}.html"
    url_altre = f"{RUTES['botiga'][altre]}{familia['slug']}.html"
    categoria = categories.get(familia.get("category")) or {}
    nom = familia["name"]
    contacte = "/contacte.html" if idioma == "ca" else "/es/contacto.html"

    # Cada variant amb la seva foto, si en té; si no, la primera de la família
    for v in familia["variants"]:
        propies = fotos_per_ref.get(v["ref"]) or []
        v["_foto"] = propies[0] if propies else (fotos[0] if fotos else None)
        v["_etiqueta"] = etiqueta_variant(nom, v["variant"])

    totes = fotos + [v["_foto"] for v in familia["variants"] if v["_foto"]]
    vistes = []
    for f in totes:
        if f and f not in vistes:
            vistes.append(f)

    galeria = ""
    if vistes:
        mines = "" if len(vistes) < 2 else "".join(
            f'<button type="button" class="mini{" actiu" if n == 0 else ""}" data-foto="{esc(f)}">'
            f'<img src="{esc(f)}" alt="" loading="lazy" width="64" height="64"></button>'
            for n, f in enumerate(vistes[:8]))
        galeria = (
            '<figure class="foto-producte">\n'
            f'                <img id="foto-gran" src="{esc(vistes[0])}" alt="{esc(nom)}" loading="eager">\n'
            + (f'                <div class="mines">{mines}</div>\n' if mines else "")
            + "            </figure>"
        )

    """
    Les opcions porten el preu escrit al text i no només a l'atribut.

    Sense javascript el desplegable no canvia res, però el preu de cada
    model segueix sent allà i es pot llegir. Qui ve de Google, i Google
    mateix, hi troben la gamma sencera.
    """
    opcions = []
    for n, v in enumerate(familia["variants"]):
        """
        Els atributs de l'opció porten `v-` al davant a posta.

        `data-foto` és de les miniatures de la galeria i `data-preu` és del
        preu que es refresca: si les opcions els fessin servir, la galeria
        els posaria un clic a sobre i el refresc hi buscaria un preu.
        """
        dades = [
            f'value="{esc(v["ref"])}"',
            f'data-v-preu="{v["price_with_vat"]:.2f}"',
            f'data-v-sense="{v["price"]:.2f}"',
            f'data-v-estat="{esc(v.get("availability") or "unknown")}"',
            f'data-v-nom="{esc(nom)} · {esc(v["_etiqueta"])}"',
        ]
        if v.get("pvpr_with_vat"):
            dades.append(f'data-v-pvpr="{v["pvpr_with_vat"]:.2f}"')
        if v["_foto"]:
            dades.append(f'data-v-foto="{esc(v["_foto"])}"')
        if n == 0:
            dades.append("selected")
        opcions.append(f'<option {" ".join(dades)}>'
                       f'{esc(v["_etiqueta"])} — {euros(v["price_with_vat"])}</option>')

    primera = familia["variants"][0]
    estat = t[ESTAT.get(primera.get("availability"), "preguntar")]
    wa = esc("https://wa.me/34711550872?text=" + urllib.parse.quote(
        t["wa_text"].format(nom=f'{nom} · {primera["_etiqueta"]}', ref=primera["ref"])))
    cos_md = markdown.a_html(familia.get("body") or "") if familia.get("body") else ""

    """
    Per a Google, una família és un ProductGroup amb les variants a dins:
    així entén que són el mateix article en models diferents i no sis
    productes que es repeteixen.
    """
    schema = {
        "@context": "https://schema.org",
        "@type": "ProductGroup",
        "name": nom,
        "description": familia.get("summary") or familia.get("body") or nom,
        "brand": {"@type": "Brand", "name": familia["brand"]} if familia.get("brand") else None,
        "image": [f"{DOMINI}{f}" for f in vistes] or None,
        "url": f"{DOMINI}{url}",
        "hasVariant": [{
            "@type": "Product",
            "name": f"{nom} · {v['_etiqueta']}",
            "sku": v["ref"],
            "image": f"{DOMINI}{v['_foto']}" if v["_foto"] else None,
            "offers": {
                "@type": "Offer",
                "url": f"{DOMINI}{url}",
                "priceCurrency": "EUR",
                "price": f"{v['price_with_vat']:.2f}",
                "availability": "https://schema.org/InStock" if v.get("availability") == "in_stock"
                                else "https://schema.org/PreOrder",
                "seller": {"@type": "LocalBusiness", "name": "mtic"},
            },
        } for v in familia["variants"]],
    }
    for variant in schema["hasVariant"]:
        if variant["image"] is None:
            del variant["image"]
    schema = {k: v for k, v in schema.items() if v is not None}

    cos = f"""        <section class="seccio">
        <div class="container">
            <nav class="molles" aria-label="{'Molles de pa' if idioma == 'ca' else 'Migas de pan'}">
                <a href="{'/' if idioma == 'ca' else '/es/'}">{t['inici']}</a><span>·</span>
                <a href="{RUTES['botiga'][idioma]}">{'Botiga' if idioma == 'ca' else 'Tienda'}</a>
                {f'<span>·</span><span>{esc(categoria.get("name", ""))}</span>' if categoria else ''}
            </nav>

            <div class="producte" data-familia>
            {galeria}
                <div class="producte-dades">
                    <h1>{esc(nom)}</h1>
                    {f'<p class="entradeta">{esc(familia["summary"])}</p>' if familia.get('summary') else ''}
                    {distintius(idioma, familia)}

                    <div class="tria">
                        <label for="variant">{t['variant']}</label>
                        <select id="variant" data-variants>
                            {"".join(opcions)}
                        </select>
                    </div>

                    <p class="preu" data-preu-ref="{esc(primera['ref'])}">
                        <strong data-preu>{euros(primera['price_with_vat'])}</strong>
                        <s class="abans" data-pvpr{'' if primera.get('pvpr_with_vat') else ' hidden'}>
                            {euros(primera['pvpr_with_vat']) if primera.get('pvpr_with_vat') else ''}</s>
                        <span class="preu-nota">{t['preu_iva']} · <span data-preu-sense>{euros(primera['price'])}</span> {t['preu_sense']}</span>
                    </p>
                    <p class="estat" data-estat-ref="{esc(primera['ref'])}"
                       data-in_stock="{esc(t['tenim'])}" data-on_order="{esc(t['demanar'])}"
                       data-unknown="{esc(t['preguntar'])}">{esc(estat)}</p>
                    <p class="botons">
                        <a class="boto" data-wa href="{wa}" target="_blank" rel="noopener">{t['demana']}</a>
                        <button type="button" class="boto-linia afegir" data-carro-afegeix
                                data-ref="{esc(primera['ref'])}"
                                data-nom="{esc(nom)} · {esc(primera['_etiqueta'])}"
                                data-preu="{primera['price_with_vat']:.2f}">{t['afegir']}</button>
                        <a class="boto-linia" href="{contacte}">{t['contacta']}</a>
                    </p>
                    <p class="ref-petita">{t['ref']}: <code data-ref>{esc(primera['ref'])}</code></p>
                </div>
            </div>

            {f'<div class="text-llarg descripcio-producte">{cos_md}</div>' if cos_md else ''}

            <p class="actualitzat">{t['orientatiu'].format(data=datetime.date.today().strftime('%d/%m/%Y'))}</p>
            <p><a href="{RUTES['botiga'][idioma]}">← {t['tornar']}</a></p>
        </div>
    </section>"""

    extra = ('    <script type="application/ld+json">\n' + json_ld(schema) + "\n    </script>\n")
    return url, pagina(idioma, url, url_altre,
                       f"{nom} · mtic",
                       familia.get("summary") or f"{nom}. {t['botiga_descripcio']}",
                       cos, seccio="botiga", imatge=vistes[0] if vistes else None, dades_extra=extra)


def preu_html(producte, classe="preu"):
    """
    El preu tal com es veu: el que es paga i, si n'hi ha, el que costava.

    El preu recomanat només arriba aquí si és més alt que el meu —l'ERP ja
    ho mira—, així que si hi és, es ratlla.
    """
    ref = esc(producte["ref"])
    parts = [f'<strong data-preu>{euros(producte["price_with_vat"])}</strong>']
    if producte.get("pvpr_with_vat"):
        parts.append(f'<s class="abans">{euros(producte["pvpr_with_vat"])}</s>')
    return f'<span class="{classe}" data-preu-ref="{ref}">' + "".join(parts) + "</span>"


def distintius(idioma, producte):
    """Els distintius que van a sobre de la foto: destacat i oferta."""
    t = T[idioma]
    fora = []
    if producte.get("featured"):
        fora.append(f'<span class="marca destacat">{ESTRELLA} {t["destacat"]}</span>')
    if producte.get("offer"):
        fora.append(f'<span class="marca oferta">{t["oferta"]}</span>')
    return f'<span class="marques">{"".join(fora)}</span>' if fora else ""


def boto_afegir(idioma, producte):
    """El botó d'afegir-lo al carro. El carro viu al navegador de qui mira."""
    t = T[idioma]
    return (f'<button type="button" class="boto-linia afegir" data-carro-afegeix'
            f' data-ref="{esc(producte["ref"])}" data-nom="{esc(producte["name"])}"'
            f' data-preu="{producte["price_with_vat"]:.2f}">{t["afegir"]}</button>')


def targeta(idioma, producte, fotos, amb_enllac):
    """
    Una targeta del llistat.

    No és un enllaç per fora: a dins hi ha el botó d'afegir al carro, i un
    botó dins d'un enllaç no es pot fer. L'enllaç envolta la foto i el nom,
    que és el que es clica per anar a la fitxa.
    """
    url = f"{RUTES['botiga'][idioma]}{producte['slug']}.html"
    foto = fotos[0] if fotos else None
    nom = esc(producte["name"])
    imatge = (f'<img src="{esc(foto)}" alt="{nom}" loading="lazy">' if foto
              else '<span class="sense-foto" aria-hidden="true"></span>')
    # Per al cercador: el que s'hi busca, tot junt i sense accents dolents
    cerca = esc(f'{producte["name"]} {producte["ref"]} {producte.get("brand") or ""}'.lower())

    dades = (f'data-categoria="{esc(producte.get("category") or "")}" data-cerca="{cerca}"'
             f'{" data-destacat" if producte.get("featured") else ""}'
             f'{" data-oferta" if producte.get("offer") else ""}')

    if amb_enllac:
        return (f'<div class="article-botiga" {dades}>'
                f'<a class="cap" href="{url}">'
                f'<span class="foto">{imatge}{distintius(idioma, producte)}</span>'
                f'<span class="nom">{nom}</span></a>'
                f'{preu_html(producte)}{boto_afegir(idioma, producte)}</div>')

    # Les famílies que no mereixen fitxa pròpia: només la fila
    return (f'<div class="article-botiga fila" {dades}>'
            f'<span class="foto">{imatge}</span>'
            f'<span class="nom">{nom}</span>'
            f'{preu_html(producte)}{boto_afegir(idioma, producte)}</div>')


def targeta_familia(idioma, familia, fotos):
    """
    Una família al llistat: una targeta, no sis.

    El preu és el de la variant més barata, amb el «des de» al davant. Porta
    la referència d'aquella variant perquè el preu es refresqui sol com el de
    qualsevol altra targeta.
    """
    t = T[idioma]
    url = f"{RUTES['botiga'][idioma]}{familia['slug']}.html"
    foto = fotos[0] if fotos else None
    nom = esc(familia["name"])
    imatge = (f'<img src="{esc(foto)}" alt="{nom}" loading="lazy">' if foto
              else '<span class="sense-foto" aria-hidden="true"></span>')

    # Al cercador s'hi ha de poder trobar per qualsevol de les variants
    paraules = " ".join([familia["name"], familia.get("brand") or ""]
                        + [f'{v["variant"]} {v["ref"]}' for v in familia["variants"]])
    dades = (f'data-categoria="{esc(familia.get("category") or "")}" data-cerca="{esc(paraules.lower())}"'
             f'{" data-destacat" if familia.get("featured") else ""}'
             f'{" data-oferta" if familia.get("offer") else ""}')

    barata = min(familia["variants"], key=lambda v: v["price_with_vat"])
    preu = (f'<span class="preu" data-preu-ref="{esc(barata["ref"])}">'
            f'<span class="des-de-text">{t["des_de"]}</span> '
            f'<strong data-preu>{euros(familia["price_from_with_vat"])}</strong></span>')

    return (f'<div class="article-botiga" {dades}>'
            f'<a class="cap" href="{url}">'
            f'<span class="foto">{imatge}{distintius(idioma, familia)}</span>'
            f'<span class="nom">{nom}</span></a>'
            f'{preu}'
            f'<a class="boto-linia afegir" href="{url}">{t["variants"]}</a></div>')


def index_botiga(idioma, cataleg, fotos_per_ref, fotos_per_familia):
    t = T[idioma]
    url = RUTES["botiga"][idioma]
    url_altre = RUTES["botiga"]["es" if idioma == "ca" else "ca"]
    categories = {c["slug"]: c for c in cataleg["categories"]}

    filtres = [f'<button type="button" class="filtre actiu" data-filtra="">{t["categoria_tot"]}</button>']
    if any(p.get("offer") for p in cataleg["products"] + (cataleg.get("groups") or [])):
        filtres.append(f'<button type="button" class="filtre" data-filtra="oferta">{t["nomes_ofertes"]}</button>')
    filtres += [f'<button type="button" class="filtre" data-filtra="{esc(c["slug"])}">{esc(c["name"])} '
                f'<span>{esc(c["count"])}</span></button>' for c in cataleg["categories"]]

    # Dues llistes i no una: les famílies que no mereixen fitxa pròpia són
    # files amples, i barrejades amb les targetes quedaven estretes i amb el
    # botó sortint per fora de la caixa.
    fitxes, files = [], []

    # Les famílies van primer: són una pàgina sencera i no una fila
    for familia in cataleg.get("groups") or []:
        fitxes.append(targeta_familia(idioma, familia, fotos_per_familia.get(familia["slug"], [])))

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
            <div class="cercador">
                <input id="cerca-botiga" type="search" data-cerca-botiga aria-label="{t['cerca']}"
                       placeholder="{t['cerca']}" autocomplete="off">
            </div>
            <div class="filtres">
                {"".join(filtres)}
            </div>
            <p class="cap-resultat" hidden data-cap-resultat>{t['cap_resultat']}</p>
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

def neteja_orfes(esperades):
    """
    Treu les pàgines que ja no hauria d'haver-hi.

    Una fitxa és un fitxer, i canviar el títol d'un producte li canvia
    l'adreça: la pàgina vella es quedava al seu lloc per sempre, amb el preu
    del dia que es va escriure. Això no és només brutícia: és una pàgina
    nostra, pública i indexable, que diu un preu que ja no és veritat, i a
    Google li sembla contingut duplicat de la bona.

    Només es mira dins de les carpetes de la botiga i dels articles, només
    els .html que hi ha just a dins, i mai l'índex.
    """
    """
    I si no s'espera res, no es treu res.

    Una resposta buida de l'ERP —mig trencada, o amb un error que no ha fet
    petar res— esborraria la botiga sencera. Buidar-la de debò es fa
    despublicant els productes un per un, i llavors ja no quedaria cap
    pàgina a mig camí.
    """
    if not esperades:
        return []

    fora = []
    carpetes = [RUTES[s][i] for s in ("botiga", "articles") for i in ("ca", "es")]

    for carpeta in carpetes:
        cami = os.path.join(ARREL, carpeta.strip("/"))
        if not os.path.isdir(cami):
            continue
        for nom in sorted(os.listdir(cami)):
            if not nom.endswith(".html") or nom == "index.html":
                continue
            url = f"{carpeta}{nom}"
            if url in esperades:
                continue
            os.remove(os.path.join(cami, nom))
            fora.append(url)

    return fora


def main():
    local = "--local" in sys.argv

    if local:
        cataleg, articles = llegeix_json("botiga.json"), llegeix_json("articles.json")
    else:
        cataleg, articles = demana("/api/build/cataleg"), demana("/api/build/articles")

    # El que tingui una adreça rara no es dibuixa: vegeu slug_segur()
    for nom, llista, clau in (("producte", cataleg["products"], "slug"),
                              ("família", cataleg.setdefault("groups", []), "slug"),
                              ("article", articles["posts"], "slug")):
        dolents = [x for x in llista if not slug_segur(x.get(clau))]
        for x in dolents:
            print(f"  ! {nom} amb adreça no vàlida, no es publica: {x.get(clau)!r}")
            llista.remove(x)

    """
    Les fotos, un cop.

    La mateixa serveix per a les dues llengües, i una adreça que ja s'ha
    baixat no es torna a demanar encara que surti a dos llocs: les variants
    d'una família i la família mateixa solen ensenyar les mateixes fotos, i
    sense això quedaven desades dues vegades amb noms diferents.
    """
    fotos_per_ref = {}
    ja_baixades = {}

    def copies_de(coses, origens, arrel):
        fetes = []
        for n, origen in enumerate(origens or [], start=1):
            if origen in ja_baixades:
                copia = ja_baixades[origen]
            else:
                # Compte amb el nom: `local` ja vol dir «sense xarxa» aquí dins
                copia = baixa_foto(origen, arrel if n == 1 else f"{arrel}-{n}")
                ja_baixades[origen] = copia
            if copia:
                fetes.append(copia)
        return fetes

    def arrel_de(text):
        return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

    # Les variants també en tenen: el desplegable canvia la foto en triar-les
    tot = cataleg["products"] + [v for g in cataleg["groups"] for v in g["variants"]]
    for producte in tot:
        baixades = copies_de(producte, producte.get("images"), arrel_de(producte["ref"]))
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

    # Les de les famílies, igual: la pàgina de la família té la seva pròpia
    # foto i no la d'una variant qualsevol
    fotos_per_familia = {}
    for familia in cataleg["groups"]:
        baixades = copies_de(familia, familia.get("images"), f"fam-{arrel_de(familia['slug'])}")
        fotos_per_familia[familia["slug"]] = baixades
        familia["images"] = baixades

    if not local:
        desa_json("botiga.json", cataleg)
        desa_json("articles.json", articles)

    canvis = []
    pagines = []          # per al sitemap: (url_ca, url_es)
    esperades = set()     # el que ha d'existir; la resta, fora

    for idioma in ("ca", "es"):
        url, text = index_botiga(idioma, cataleg, fotos_per_ref, fotos_per_familia)
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
            esperades.add(url)
            if escriu(url, text):
                canvis.append(url)
        pagines.append((urls["ca"], urls["es"]))

    # Les pàgines de família
    for familia in cataleg["groups"]:
        urls = {}
        for idioma in ("ca", "es"):
            url, text = fitxa_familia(idioma, familia, categories,
                                      fotos_per_familia.get(familia["slug"], []),
                                      fotos_per_ref)
            urls[idioma] = url
            esperades.add(url)
            if escriu(url, text):
                canvis.append(url)
        pagines.append((urls["ca"], urls["es"]))

    for post in articles["posts"]:
        url, text = fitxa_article(post["lang"], post)
        esperades.add(url)
        if escriu(url, text):
            canvis.append(url)
        parella = post.get("translation")
        if post["lang"] == "ca":
            altre = f"{RUTES['articles']['es']}{parella['slug']}.html" if parella else None
            pagines.append((url, altre))
        elif not parella:
            # Un article només en castellà també ha de sortir al sitemap
            pagines.append((None, url))

    orfes = neteja_orfes(esperades)

    # El sitemap el fa web.py: aquí només se li diu quines pàgines hi ha més
    desa_json("pagines.json", [{"ca": ca, "es": es} for ca, es in pagines])
    web.main()

    for o in orfes:
        print(f"  − {o} (ja no hi ha res que hi correspongui)")
    print(f"{len(canvis)} pàgines generades o canviades" +
          (f", {len(orfes)} tretes." if orfes else "."))
    for c in canvis[:40]:
        print("  ·", c)
    if len(canvis) > 40:
        print(f"  … i {len(canvis) - 40} més")


if __name__ == "__main__":
    main()
