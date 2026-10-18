#!/usr/bin/env python3
"""
mtic · el tros de markdown que fem servir als articles.

No és un markdown sencer i no ho vol ser: és el que s'escriu de debò en un
article del blog —títols, paràgrafs, negreta, cursiva, enllaços, imatges,
llistes, cites i codi— i prou. Sense dependències, com la resta del
repositori.

Tot el text s'escapa ABANS de posar-hi format, així que un article no pot
portar HTML a dins ni per error ni a posta. Si algun dia cal una taula o un
vídeo, s'afegeix aquí i es veu a totes les pàgines alhora.
"""
import html
import re

# ------------------------------------------------------------- en línia

# L'ordre importa: el codi va primer perquè dins seu no s'hi posa res més.
RE_CODI = re.compile(r"`([^`]+)`")
RE_IMATGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
RE_ENLLAC = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
RE_NEGRETA = re.compile(r"\*\*([^*]+)\*\*")
RE_CURSIVA = re.compile(r"(?<![*\w])\*([^*]+)\*(?!\*)")

# Només enllaços que porten a algun lloc de debò: res de javascript: ni data:
RE_ADRECA_BONA = re.compile(r"^(https?://|/|#|mailto:|tel:)")


def _adreca(url):
    url = url.strip()
    return url if RE_ADRECA_BONA.match(url) else "#"


def en_linia(text):
    """El format que va dins d'una línia.

    S'escapa AQUÍ i no abans: els blocs es llegeixen del text tal com s'ha
    escrit, perquè una cita comença per «>» i, escapant-ho tot d'entrada,
    el «>» ja no hi era quan tocava mirar-lo.
    """
    # quote=True, i no és un detall: el text acaba dins d'atributs (alt="…",
    # href="…"). Amb una cometa sense escapar, un peu de foto com
    #   ![Foto " onerror=alert(1) x](/a.jpg)
    # se surt de l'atribut i el navegador executa el que hi hagi darrere.
    text = html.escape(str(text), quote=True)
    trossos = []

    def guarda(m):
        trossos.append(f"<code>{m.group(1)}</code>")
        return f"\x00{len(trossos) - 1}\x00"

    text = RE_CODI.sub(guarda, text)
    text = RE_IMATGE.sub(
        lambda m: f'<img src="{_adreca(m.group(2))}" alt="{m.group(1)}" loading="lazy">', text)
    text = RE_ENLLAC.sub(
        lambda m: f'<a href="{_adreca(m.group(2))}">{m.group(1)}</a>', text)
    text = RE_NEGRETA.sub(r"<strong>\1</strong>", text)
    text = RE_CURSIVA.sub(r"<em>\1</em>", text)

    return re.sub(r"\x00(\d+)\x00", lambda m: trossos[int(m.group(1))], text)


# --------------------------------------------------------------- blocs

RE_TITOL = re.compile(r"^(#{1,4})\s+(.*)$")
RE_LLISTA = re.compile(r"^[-*]\s+(.*)$")
RE_NUMERADA = re.compile(r"^\d+[.)]\s+(.*)$")
RE_CITA = re.compile(r"^>\s?(.*)$")


def a_html(text):
    """Markdown -> HTML. Torna una cadena amb els blocs un per línia."""
    linies = str(text or "").replace("\r\n", "\n").split("\n")
    sortida = []
    paragraf = []
    llista = None          # 'ul' | 'ol' | None
    cita = []
    codi = None            # llista de línies dins d'un bloc ```

    def tanca_paragraf():
        nonlocal paragraf
        if paragraf:
            sortida.append(f"<p>{en_linia(' '.join(paragraf))}</p>")
            paragraf = []

    def tanca_llista():
        nonlocal llista
        if llista:
            sortida.append(f"</{llista}>")
            llista = None

    def tanca_cita():
        nonlocal cita
        if cita:
            sortida.append(f"<blockquote><p>{en_linia(' '.join(cita))}</p></blockquote>")
            cita = []

    def tanca_tot():
        tanca_paragraf()
        tanca_llista()
        tanca_cita()

    for linia in linies:
        net = linia.rstrip()

        # Bloc de codi: a dins no s'hi toca res
        if net.strip().startswith("```"):
            if codi is None:
                tanca_tot()
                codi = []
            else:
                sortida.append("<pre><code>" + html.escape("\n".join(codi), quote=False) + "</code></pre>")
                codi = None
            continue
        if codi is not None:
            codi.append(net)
            continue

        if not net.strip():
            tanca_tot()
            continue

        titol = RE_TITOL.match(net)
        if titol:
            tanca_tot()
            # Un article ja porta el seu <h1>: el # de dins comença a h2
            nivell = min(len(titol.group(1)) + 1, 5)
            sortida.append(f"<h{nivell}>{en_linia(titol.group(2).strip())}</h{nivell}>")
            continue

        if net.strip() in ("---", "***", "___"):
            tanca_tot()
            sortida.append("<hr>")
            continue

        cita_m = RE_CITA.match(net.strip())
        if cita_m:
            tanca_paragraf()
            tanca_llista()
            cita.append(cita_m.group(1).strip())
            continue
        tanca_cita()

        for regex, etiqueta in ((RE_LLISTA, "ul"), (RE_NUMERADA, "ol")):
            punt = regex.match(net.strip())
            if punt:
                tanca_paragraf()
                if llista != etiqueta:
                    tanca_llista()
                    sortida.append(f"<{etiqueta}>")
                    llista = etiqueta
                sortida.append(f"<li>{en_linia(punt.group(1).strip())}</li>")
                break
        else:
            tanca_llista()
            paragraf.append(net.strip())
            continue

    if codi is not None:
        sortida.append("<pre><code>" + html.escape("\n".join(codi), quote=False) + "</code></pre>")
    tanca_tot()
    return "\n".join(sortida)


def nomes_text(text, llargada=200):
    """El resum per a les metaetiquetes quan l'article no en porta cap."""
    pla = re.sub(r"<[^>]+>", " ", a_html(text))
    pla = html.unescape(re.sub(r"\s+", " ", pla)).strip()
    return pla if len(pla) <= llargada else pla[:llargada - 1].rsplit(" ", 1)[0] + "…"
