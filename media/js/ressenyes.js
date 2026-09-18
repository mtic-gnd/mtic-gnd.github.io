/*
 * mtic · Ressenyes de Google
 * ---------------------------------------------------------------
 * Dues maneres de mostrar ressenyes (tria'n una):
 *
 * A) AUTOMÀTIC (recomanat): posa una clau de l'API de Google Places
 *    a CONFIG.clauApi. Les ressenyes es carreguen en directe de Google
 *    (Google en retorna un màxim de 5, les més rellevants).
 *    Instruccions a LLEGEIX-ME-SEO.md.
 *
 * B) MANUAL: deixa clauApi buida i copia les teves ressenyes reals
 *    de Google a CONFIG.manual (valoració, total i textos).
 *
 * Si no hi ha res configurat, es mostra un bloc amb botons per
 * llegir i escriure ressenyes a Google.
 */
var CONFIG = {
    placeId: "ChIJF6i-5AbFoBIRn7OY2C0bg0o",
    clauApi: "",
    manual: {
        valoracio: null,        // p. ex. 5.0
        total: null,            // p. ex. 12
        ressenyes: [
            { autor: "Laia Caldú Martí", estrelles: 5, text: "Tot correcte! Molt professional! :)", quan: "fa 5 mesos" },
            { autor: "Pepi Mulet", estrelles: 5, text: "Super contenta per la compra Però el que vull destacar especialment és el tracte del venedor. Ha estat molt atent, amable i professional en tot moment. Ha respost ràpidament als meus dubtes i m’ha ajudat en tot el que he necessitat. És un plaer trobar venedors així, que es preocupen pels seus clients.moltes gracies", quan: "fa 1 dia" },
            { autor: "Mònica Miró", estrelles: 5, text: "La meva experiència ha estat molt positiva tant en la rapidesa amb la que m’ha solucionat el problema com amb el tracte rebut. Repetirem😉", quan: "fa 1 dia" },
            // { autor: "Nom Cognom", estrelles: 5, text: "Text de la ressenya…", quan: "fa 2 setmanes" },
        ]
    }
};

(function () {
    var arrel = document.getElementById("ressenyes-google");
    if (!arrel) return;
    var zonaNota = arrel.querySelector("[data-nota]");
    var zonaLlista = arrel.querySelector("[data-llista]");
    var zonaFont = arrel.querySelector("[data-font]");

    var ESTRELLA = '<svg viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="M10 1.5l2.6 5.5 6 .7-4.4 4.1 1.2 5.9L10 14.8l-5.4 2.9 1.2-5.9L1.4 7.7l6-.7z"/></svg>';

    function esc(s) {
        return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }
    function estrelles(n) {
        var h = "";
        for (var i = 1; i <= 5; i++) h += i <= Math.round(n) ? ESTRELLA : ESTRELLA.replace("<svg", '<svg class="buida"');
        return '<span class="estrelles" role="img" aria-label="' + n + ' de 5 estrelles">' + h + "</span>";
    }
    function nota(valor, total) {
        if (!valor) return;
        var v = Number(valor).toFixed(1).replace(".", ",");
        zonaNota.innerHTML =
            '<div class="nota-google"><span class="xifra">' + v + '</span><div>' + estrelles(valor) +
            '<div class="detall">' + (total ? total + (total == 1 ? " ressenya" : " ressenyes") + " a Google" : "a Google") + "</div></div></div>";
    }
    function targeta(r) {
        var foto = r.foto
            ? '<img src="' + esc(r.foto) + '" alt="" width="40" height="40" loading="lazy" referrerpolicy="no-referrer">'
            : '<span class="inicial" aria-hidden="true">' + esc((r.autor || "?").charAt(0).toUpperCase()) + "</span>";
        var nom = r.enllac ? '<a href="' + esc(r.enllac) + '" target="_blank" rel="noopener nofollow">' + esc(r.autor) + "</a>" : esc(r.autor);
        return '<article class="ressenya">' + estrelles(r.estrelles) +
            '<blockquote class="retallat">' + esc(r.text) + "</blockquote>" +
            '<div class="autor">' + foto + "<div><strong>" + nom + "</strong><span>" + esc(r.quan || "") + "</span></div></div></article>";
    }
    function pinta(llista) {
        llista = llista.filter(function (r) { return r.text; });
        if (!llista.length) return false;
        zonaLlista.innerHTML = '<div class="llista-ressenyes">' + llista.map(targeta).join("") + "</div>";
        return true;
    }

    // Mode manual
    function manual() {
        var m = CONFIG.manual;
        nota(m.valoracio, m.total);
        pinta(m.ressenyes || []);
    }

    // Mode automàtic (Google Places API New). Només es crida quan la secció és a prop de la pantalla.
    function automatic() {
        fetch("https://places.googleapis.com/v1/places/" + CONFIG.placeId + "?languageCode=ca", {
            headers: {
                "X-Goog-Api-Key": CONFIG.clauApi,
                "X-Goog-FieldMask": "rating,userRatingCount,reviews"
            }
        })
            .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
            .then(function (d) {
                nota(d.rating, d.userRatingCount);
                var ok = pinta((d.reviews || []).map(function (r) {
                    var a = r.authorAttribution || {};
                    return {
                        autor: a.displayName, enllac: a.uri, foto: a.photoUri, estrelles: r.rating,
                        text: (r.originalText && r.originalText.text) || (r.text && r.text.text),
                        quan: r.relativePublishTimeDescription
                    };
                }));
                if (ok && zonaFont) zonaFont.hidden = false;
            })
            .catch(function (e) { console.warn("Ressenyes de Google no disponibles:", e); manual(); });
    }

    var carrega = CONFIG.clauApi ? automatic : manual;
    if ("IntersectionObserver" in window && CONFIG.clauApi) {
        var io = new IntersectionObserver(function (entrades) {
            if (entrades[0].isIntersecting) { io.disconnect(); carrega(); }
        }, { rootMargin: "400px" });
        io.observe(arrel);
    } else {
        carrega();
    }
})();
