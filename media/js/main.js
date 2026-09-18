/* mtic · menú mòbil, formulari de contacte i any del peu */
(function () {
    var TELEFON_WA = "34711550872";
    var CORREU = "info@mtic.cat";

    // Menú mòbil
    var boto = document.querySelector(".menu-obre");
    var menu = document.getElementById("menu");
    if (boto && menu) {
        boto.addEventListener("click", function () {
            var obert = menu.classList.toggle("obert");
            boto.setAttribute("aria-expanded", obert ? "true" : "false");
        });
    }

    // Any actual al peu
    document.querySelectorAll("[data-any]").forEach(function (el) {
        el.textContent = new Date().getFullYear();
    });

    // Formulari: envia per WhatsApp o per correu
    var form = document.getElementById("formulari-contacte");
    if (!form) return;

    function missatge() {
        var nom = form.nom.value.trim();
        var servei = form.servei.value;
        var text = form.missatge.value.trim();
        var parts = ["Hola mtic! Sóc " + nom + "."];
        if (servei) parts.push("Consulta sobre: " + servei + ".");
        parts.push(text);
        if (form.telefon.value.trim()) parts.push("El meu telèfon: " + form.telefon.value.trim());
        return parts.join("\n\n");
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        if (!form.reportValidity()) return;
        var via = (e.submitter && e.submitter.value) || "whatsapp";
        var cos = missatge();
        if (via === "correu") {
            var assumpte = "Consulta web" + (form.servei.value ? " – " + form.servei.value : "");
            window.location.href = "mailto:" + CORREU + "?subject=" + encodeURIComponent(assumpte) + "&body=" + encodeURIComponent(cos);
        } else {
            window.open("https://wa.me/" + TELEFON_WA + "?text=" + encodeURIComponent(cos), "_blank", "noopener");
        }
    });
})();
