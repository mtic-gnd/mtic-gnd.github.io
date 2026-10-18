/* mtic · menú mòbil, formulari de contacte, any del peu, avís de cookies i mesura de conversions */
(function () {
    var TELEFON_WA = "34711550872";
    var CORREU = "info@mtic.cat";
    var GA_ID = "G-520567YS7Q";
    var CLAU_COOKIES = "mtic-cookies"; // "si" | "no"
    var ES = (document.documentElement.lang || "ca").indexOf("es") === 0;

    var T = ES ? {
        avis: "Usamos cookies de Google Analytics para saber cómo se usa la web y mejorarla. Solo se activan si las aceptas.",
        mesInfo: "Más información",
        urlCookies: "/es/cookies.html",
        acceptar: "Aceptar",
        rebutjar: "Rechazar",
        etiqueta: "Aviso de cookies",
        hola: "¡Hola mtic! Soy ",
        consulta: "Consulta sobre: ",
        telefon: "Mi teléfono: ",
        assumpte: "Consulta web"
    } : {
        avis: "Fem servir galetes de Google Analytics per saber com s'utilitza la web i millorar-la. Només s'activen si les acceptes.",
        mesInfo: "Més informació",
        urlCookies: "/cookies.html",
        acceptar: "Accepto",
        rebutjar: "Rebutjo",
        etiqueta: "Avís de galetes",
        hola: "Hola mtic! Sóc ",
        consulta: "Consulta sobre: ",
        telefon: "El meu telèfon: ",
        assumpte: "Consulta web"
    };

    // ---------- Google Analytics amb consentiment previ (Consent Mode v2, mode bàsic) ----------
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
    gtag("consent", "default", {
        ad_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied",
        analytics_storage: "denied"
    });

    var analiticaActiva = false;
    function llegeix() { try { return localStorage.getItem(CLAU_COOKIES); } catch (e) { return null; } }
    function desa(v) { try { localStorage.setItem(CLAU_COOKIES, v); } catch (e) { } }

    function activaAnalitica() {
        if (analiticaActiva) return;
        analiticaActiva = true;
        gtag("consent", "update", { analytics_storage: "granted" });
        gtag("js", new Date());
        gtag("config", GA_ID);
        var s = document.createElement("script");
        s.async = true;
        s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_ID;
        document.head.appendChild(s);
    }

    function tancaAvis() {
        var a = document.querySelector(".avis-cookies");
        if (a) a.remove();
    }

    function mostraAvis() {
        tancaAvis();
        var a = document.createElement("div");
        a.className = "avis-cookies";
        a.setAttribute("role", "region");
        a.setAttribute("aria-label", T.etiqueta);
        a.innerHTML = '<p>' + T.avis + ' <a href="' + T.urlCookies + '">' + T.mesInfo + '</a>.</p>' +
            '<div class="botons"><button type="button" class="boto" data-cookies="si">' + T.acceptar + '</button>' +
            '<button type="button" class="boto-linia" data-cookies="no">' + T.rebutjar + '</button></div>';
        a.addEventListener("click", function (e) {
            var b = e.target.closest("[data-cookies]");
            if (!b) return;
            var v = b.getAttribute("data-cookies");
            desa(v);
            tancaAvis();
            if (v === "si") {
                activaAnalitica();
            } else if (analiticaActiva) {
                gtag("consent", "update", { analytics_storage: "denied" });
            }
        });
        document.body.appendChild(a);
    }

    var decisio = llegeix();
    if (decisio === "si") activaAnalitica();
    else if (decisio !== "no") mostraAvis();

    // Botó del peu per canviar la decisió
    document.addEventListener("click", function (e) {
        if (e.target.closest("[data-obre-cookies]")) { e.preventDefault(); mostraAvis(); }
    });

    // ---------- Conversions: clics a telèfon, WhatsApp i correu ----------
    function esdeveniment(nom, params) {
        if (analiticaActiva) gtag("event", nom, params || {});
    }
    document.addEventListener("click", function (e) {
        var a = e.target.closest("a[href]");
        if (!a) return;
        var href = a.getAttribute("href");
        var on = { pagina: location.pathname, ubicacio: a.closest("header") ? "capcalera" : a.closest("footer") ? "peu" : a.classList.contains("wa-flotant") ? "flotant" : "contingut" };
        if (href.indexOf("tel:") === 0) esdeveniment("clic_telefon", on);
        else if (href.indexOf("https://wa.me/") === 0) esdeveniment("clic_whatsapp", on);
        else if (href.indexOf("mailto:") === 0) esdeveniment("clic_correu", on);
    });

    // ---------- Menú mòbil ----------
    var boto = document.querySelector(".menu-obre");
    var menu = document.getElementById("menu");
    if (boto && menu) {
        boto.addEventListener("click", function () {
            var obert = menu.classList.toggle("obert");
            boto.setAttribute("aria-expanded", obert ? "true" : "false");
        });
    }

    // ---------- Any actual al peu ----------
    document.querySelectorAll("[data-any]").forEach(function (el) {
        el.textContent = new Date().getFullYear();
    });

    // ---------- Formulari: envia per WhatsApp o per correu ----------
    var form = document.getElementById("formulari-contacte");
    if (!form) return;

    function missatge() {
        var nom = form.nom.value.trim();
        var servei = form.servei.value;
        var text = form.missatge.value.trim();
        var parts = [T.hola + nom + "."];
        if (servei) parts.push(T.consulta + servei + ".");
        parts.push(text);
        if (form.telefon.value.trim()) parts.push(T.telefon + form.telefon.value.trim());
        return parts.join("\n\n");
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        if (!form.reportValidity()) return;
        var via = (e.submitter && e.submitter.value) || "whatsapp";
        var cos = missatge();
        esdeveniment("enviament_formulari", { via: via, servei: form.servei.value || "" });
        if (via === "correu") {
            var assumpte = T.assumpte + (form.servei.value ? " – " + form.servei.value : "");
            window.location.href = "mailto:" + CORREU + "?subject=" + encodeURIComponent(assumpte) + "&body=" + encodeURIComponent(cos);
        } else {
            window.open("https://wa.me/" + TELEFON_WA + "?text=" + encodeURIComponent(cos), "_blank", "noopener");
        }
    });
})();
