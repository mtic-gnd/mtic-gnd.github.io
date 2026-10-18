/*
 * mtic · la botiga.
 *
 * Tres coses petites, i cap d'elles imprescindible: la pàgina ja està
 * sencera abans que això corri.
 *
 *  1. Refresca els preus. El preu que es veu és el de l'última generació,
 *     escrit dins la pàgina; aquí es demana a l'ERP si n'hi ha un de nou. Si
 *     no contesta —la llum, el túnel, el que sigui— no es toca res i ningú
 *     se n'adona. Per això es fa així i no al revés.
 *  2. Canvia la foto gran en clicar una miniatura.
 *  3. Filtra el llistat per categoria, sense recarregar.
 */
(function () {
    'use strict';

    var meta = document.querySelector('meta[name="mtic-api"]');
    var API = meta ? meta.content.replace(/\/$/, '') : '';

    function diners(valor) {
        return valor.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
    }

    function preus() {
        var caixes = document.querySelectorAll('[data-preu-ref]');
        if (!API || !caixes.length) return;

        fetch(API + '/api/public/preus', { headers: { accept: 'application/json' } })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (dades) {
                if (!dades || !dades.products) return;

                var per_ref = {};
                dades.products.forEach(function (p) { per_ref[p.ref] = p; });

                caixes.forEach(function (caixa) {
                    var nou = per_ref[caixa.dataset.preuRef];
                    if (!nou) return;
                    var gran = caixa.querySelector('[data-preu]');
                    var petit = caixa.querySelector('[data-preu-sense]');
                    if (gran) gran.textContent = diners(nou.price_with_vat);
                    if (petit) petit.textContent = diners(nou.price);
                });

                document.querySelectorAll('[data-estat-ref]').forEach(function (el) {
                    var nou = per_ref[el.dataset.estatRef];
                    if (nou && el.dataset[nou.availability]) el.textContent = el.dataset[nou.availability];
                });
            })
            .catch(function () { /* el preu imprès ja serveix */ });
    }

    function galeria() {
        var gran = document.getElementById('foto-gran');
        if (!gran) return;
        document.querySelectorAll('[data-foto]').forEach(function (boto) {
            boto.addEventListener('click', function () {
                gran.src = boto.dataset.foto;
                document.querySelectorAll('[data-foto]').forEach(function (b) {
                    b.classList.toggle('actiu', b === boto);
                });
            });
        });
    }

    function filtres() {
        var botons = document.querySelectorAll('[data-filtra]');
        if (!botons.length) return;
        botons.forEach(function (boto) {
            boto.addEventListener('click', function () {
                var tria = boto.dataset.filtra;
                botons.forEach(function (b) { b.classList.toggle('actiu', b === boto); });
                document.querySelectorAll('[data-categoria]').forEach(function (fitxa) {
                    fitxa.hidden = Boolean(tria) && fitxa.dataset.categoria !== tria;
                });
            });
        });
    }

    function engega() { preus(); galeria(); filtres(); }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', engega);
    else engega();
})();
