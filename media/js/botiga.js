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

    /*
     * Si la pagina diu que es pot enviar la comanda a l'ERP (fase 8).
     *
     * El senyal l'escriu el generador nomes amb MTIC_ORDERS=1, i de serie no
     * hi es: el carro acaba en un missatge de WhatsApp, com sempre. Si el
     * senyal hi es pero l'ERP contesta que no, el carro se'n torna al de
     * sempre sense dir res a ningu.
     */
    var COMANDES = Boolean(document.querySelector('meta[name="mtic-orders"]')) && Boolean(API);

    function diners(valor) {
        return valor.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
    }

    /*
     * Els preus que ha contestat l'ERP, guardats.
     *
     * A les pàgines de família el desplegable canvia de referència sense
     * recarregar, i llavors el preu d'aquella l'ha de treure d'aquí: tornar
     * a demanar-los cada vegada seria demanar el mateix cinc cops.
     */
    var PREUS = null;

    function pintaPreus() {
        if (!PREUS) return;

        document.querySelectorAll('[data-preu-ref]').forEach(function (caixa) {
            var nou = PREUS[caixa.dataset.preuRef];
            if (!nou) return;
            var gran = caixa.querySelector('[data-preu]');
            var petit = caixa.querySelector('[data-preu-sense]');
            if (gran) gran.textContent = diners(nou.price_with_vat);
            if (petit) petit.textContent = diners(nou.price);
        });

        document.querySelectorAll('[data-estat-ref]').forEach(function (el) {
            var nou = PREUS[el.dataset.estatRef];
            if (nou && el.dataset[nou.availability]) el.textContent = el.dataset[nou.availability];
        });
    }

    function preus() {
        var caixes = document.querySelectorAll('[data-preu-ref]');
        if (!API || !caixes.length) return;

        fetch(API + '/api/public/preus', { headers: { accept: 'application/json' } })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (dades) {
                if (!dades || !dades.products) return;
                PREUS = {};
                dades.products.forEach(function (p) { PREUS[p.ref] = p; });
                pintaPreus();
            })
            .catch(function () { /* el preu imprès ja serveix */ });
    }

    function galeria() {
        var gran = document.getElementById('foto-gran');
        if (!gran) return;
        document.querySelectorAll('.mini[data-foto]').forEach(function (boto) {
            boto.addEventListener('click', function () {
                gran.src = boto.dataset.foto;
                document.querySelectorAll('.mini[data-foto]').forEach(function (b) {
                    b.classList.toggle('actiu', b === boto);
                });
            });
        });
    }

    /*
     * El filtre de categories i el cercador són la mateixa cosa: dues
     * condicions sobre les mateixes fitxes. Es resolen juntes perquè, si no,
     * escriure al cercador desfeia el filtre i al revés.
     */
    var triaActual = '';
    var textActual = '';

    function repintaLlistat() {
        var fitxes = document.querySelectorAll('[data-categoria]');
        if (!fitxes.length) return;
        var visibles = 0;

        fitxes.forEach(function (fitxa) {
            var perCategoria = !triaActual
                || (triaActual === 'oferta' ? fitxa.hasAttribute('data-oferta')
                                            : fitxa.dataset.categoria === triaActual);
            var perText = !textActual || (fitxa.dataset.cerca || '').indexOf(textActual) !== -1;
            var surt = perCategoria && perText;
            fitxa.hidden = !surt;
            if (surt) visibles += 1;
        });

        var buit = document.querySelector('[data-cap-resultat]');
        if (buit) buit.hidden = visibles > 0;
    }

    function filtres() {
        var botons = document.querySelectorAll('[data-filtra]');
        botons.forEach(function (boto) {
            boto.addEventListener('click', function () {
                triaActual = boto.dataset.filtra;
                botons.forEach(function (b) { b.classList.toggle('actiu', b === boto); });
                repintaLlistat();
            });
        });

        var cerca = document.querySelector('[data-cerca-botiga]');
        if (cerca) {
            cerca.addEventListener('input', function () {
                textActual = cerca.value.trim().toLowerCase();
                repintaLlistat();
            });
        }
    }

    /*
     * El carro.
     *
     * No és una botiga de debò: no es paga aquí. El carro només serveix per
     * no haver d'escriure la comanda a mà, que és el que passava quan només
     * hi havia el botó de WhatsApp per article.
     *
     * Viu al navegador de qui mira (localStorage) i no surt d'allà fins que
     * ell prem el botó: llavors s'obre WhatsApp amb la llista escrita. Si el
     * navegador no deixa desar res —finestra privada, galetes bloquejades—,
     * el carro funciona igual mentre la pàgina estigui oberta.
     */
    var CLAU = 'mtic-carro';
    var TEXTOS = {
        ca: {
            titol: 'La teva comanda', buit: 'Encara no hi has posat res.',
            demanar: 'Demana-ho per WhatsApp', buidar: 'Buida el carro',
            treu: 'Treu-ho', tanca: 'Tanca', obre: 'La teva comanda',
            salutacio: 'Hola, aquesta és la comanda que voldria fer:',
            afegit: 'Afegit',
            enviar: 'Envia-la a la botiga', nom: 'El teu nom', contacte: 'Correu o telèfon',
            comentari: 'Alguna cosa més? (opcional)',
            enviant: 'Enviant…', fet: 'Rebuda! T\'escric de seguida.',
            falla: 'No s\'ha pogut enviar. La teva comanda segueix aquí: demana-la per WhatsApp amb el botó de sota.',
            cal_nom: 'Posa-hi el teu nom i una manera de contestar-te.'
        },
        es: {
            titol: 'Tu pedido', buit: 'Todavía no has puesto nada.',
            demanar: 'Pídelo por WhatsApp', buidar: 'Vacía el carrito',
            treu: 'Quítalo', tanca: 'Cerrar', obre: 'Tu pedido',
            salutacio: 'Hola, este es el pedido que querría hacer:',
            afegit: 'Añadido',
            enviar: 'Envíalo a la tienda', nom: 'Tu nombre', contacte: 'Correo o teléfono',
            comentari: '¿Algo más? (opcional)',
            enviant: 'Enviando…', fet: '¡Recibido! Te escribo enseguida.',
            falla: 'No se ha podido enviar. Tu pedido sigue aquí: pídelo por WhatsApp con el botón de abajo.',
            cal_nom: 'Pon tu nombre y una manera de contestarte.'
        }
    };

    function carro() {
        var t = TEXTOS[document.documentElement.lang === 'es' ? 'es' : 'ca'];
        var linies = llegeix();
        var panell;

        function llegeix() {
            try {
                var brut = JSON.parse(window.localStorage.getItem(CLAU) || '[]');
                return Array.isArray(brut) ? brut.filter(function (l) { return l && l.ref; }) : [];
            } catch (e) {
                return [];     // sense localStorage el carro dura el que duri la pàgina
            }
        }

        function desa() {
            try { window.localStorage.setItem(CLAU, JSON.stringify(linies)); } catch (e) { /* tant li fa */ }
            pinta();
        }

        function compta() {
            return linies.reduce(function (n, l) { return n + (Number(l.qty) || 0); }, 0);
        }

        function missatge() {
            var text = t.salutacio + '\n\n';
            linies.forEach(function (l) { text += l.qty + ' x ' + l.ref + ' — ' + l.nom + '\n'; });
            return 'https://wa.me/34711550872?text=' + encodeURIComponent(text);
        }

        // ------------------------------------------------------- la finestra
        function crea() {
            var boto = document.createElement('button');
            boto.type = 'button';
            boto.className = 'carro-boto';
            boto.setAttribute('aria-label', t.obre);
            boto.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"'
                + ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                + '<circle cx="9" cy="20" r="1"/><circle cx="18" cy="20" r="1"/>'
                + '<path d="M2 3h2l2.4 11.3a2 2 0 0 0 2 1.7h7.7a2 2 0 0 0 2-1.6L21 7H6"/></svg>'
                + '<span class="compte" data-carro-compte></span>';

            panell = document.createElement('div');
            panell.className = 'carro-panell';
            panell.hidden = true;
            panell.innerHTML = '<div class="cap"><strong>' + t.titol + '</strong>'
                + '<button type="button" class="tanca" aria-label="' + t.tanca + '">&times;</button></div>'
                + '<div class="linies" data-carro-linies></div>'
                + formulari()
                + '<div class="peu"><a class="boto" data-carro-whatsapp>' + t.demanar + '</a>'
                + '<button type="button" class="boto-linia" data-carro-buida>' + t.buidar + '</button></div>';

            document.body.appendChild(boto);
            document.body.appendChild(panell);

            boto.addEventListener('click', function () { panell.hidden = !panell.hidden; });
            panell.querySelector('.tanca').addEventListener('click', function () { panell.hidden = true; });
            panell.querySelector('[data-carro-buida]').addEventListener('click', function () {
                linies = [];
                desa();
            });

            var form = panell.querySelector('[data-carro-form]');
            if (form) {
                form.addEventListener('submit', function (e) {
                    e.preventDefault();
                    envia(form);
                });
            }

            panell.addEventListener('click', function (e) {
                var fila = e.target.closest('[data-linia]');
                if (!fila) return;
                var ref = fila.dataset.linia;
                var linia = linies.filter(function (l) { return l.ref === ref; })[0];
                if (!linia) return;

                if (e.target.closest('[data-mes]')) linia.qty += 1;
                if (e.target.closest('[data-menys]')) linia.qty -= 1;
                if (e.target.closest('[data-treu]')) linia.qty = 0;
                linies = linies.filter(function (l) { return l.qty > 0; });
                desa();
            });
        }

        /*
         * El formulari d'enviar la comanda a l'ERP.
         *
         * Nomes surt si la pagina porta el senyal. El camp `confirma` es
         * l'esquer: a la pantalla no es veu i una persona no l'omple mai;
         * si arriba ple, el servidor contesta que si i no desa res.
         */
        function formulari() {
            if (!COMANDES) return '';
            return '<form class="carro-envia" data-carro-form novalidate>'
                + '<input name="nom" required autocomplete="name" placeholder="' + t.nom + '">'
                + '<input name="contacte" required autocomplete="email" placeholder="' + t.contacte + '">'
                + '<textarea name="notes" rows="2" placeholder="' + t.comentari + '"></textarea>'
                + '<input name="confirma" tabindex="-1" autocomplete="off" aria-hidden="true"'
                + ' style="position:absolute;left:-9999px;width:1px;height:1px">'
                + '<button type="submit" class="boto">' + t.enviar + '</button>'
                + '<p class="avis" data-carro-avis hidden></p>'
                + '</form>';
        }

        /*
         * LA CLAU D'AQUEST ENVIAMENT.
         *
         * El navegador envia la comanda i espera resposta. Si la connexio es
         * talla just despres d'enviar-la —un mobil que canvia d'antena, una
         * pestanya que es tanca—, qui ho ha enviat no sap si ha arribat i
         * torna a premer. Sense clau, aixo son dues comandes iguals i algu
         * les ha de comparar a ma.
         *
         * Neix un sol cop per carro i es torna a enviar a cada intent. Quan
         * la comanda arriba de debo, s'oblida: el carro seguent n'estrena
         * una altra.
         *
         * No diu res de ningu: es un numero a l'atzar que neix i mor amb un
         * carro.
         */
        var CLAU_ENVIAMENT = 'mtic-carro-enviament';

        function clauEnviament() {
            var clau = null;
            try { clau = window.localStorage.getItem(CLAU_ENVIAMENT); } catch (e) { clau = null; }
            if (clau) return clau;

            clau = (Date.now().toString(36) + Math.random().toString(36).slice(2, 10));
            try { window.localStorage.setItem(CLAU_ENVIAMENT, clau); } catch (e) { /* res */ }
            return clau;
        }

        function oblidaClau() {
            try { window.localStorage.removeItem(CLAU_ENVIAMENT); } catch (e) { /* res */ }
        }

        /** Que s'envia: nomes referencies i quantitats. El preu el posa l'ERP. */
        function paquet(form) {
            var contacte = String(form.contacte.value || '').trim();
            var ambArrova = contacte.indexOf('@') > 0;
            return {
                name: String(form.nom.value || '').trim(),
                email: ambArrova ? contacte : '',
                phone: ambArrova ? '' : contacte,
                notes: String(form.notes.value || '').trim(),
                confirma: String(form.confirma.value || ''),
                idem_key: clauEnviament(),
                locale: document.documentElement.lang === 'es' ? 'es' : 'ca',
                lines: linies.map(function (l) {
                    return { ref: l.ref, name: l.nom, qty: l.qty, price: l.preu };
                })
            };
        }

        function envia(form) {
            var avis = form.querySelector('[data-carro-avis]');
            var boto = form.querySelector('button[type="submit"]');
            var dades = paquet(form);

            var mostra = function (text) {
                avis.textContent = text;
                avis.hidden = false;
            };

            if (!dades.name || (!dades.email && !dades.phone)) return mostra(t.cal_nom);
            if (!dades.lines.length) return mostra(t.buit);

            boto.disabled = true;
            mostra(t.enviant);

            /*
             * NOMES ES DIU «REBUDA» SI L'ERP HO HA DIT.
             *
             * Ni amb un error de xarxa, ni amb un 500, ni amb una resposta
             * que no es pot llegir. Dir que una comanda ha arribat quan no se
             * sap es la pitjor manera de perdre-la: qui l'ha feta se'n va
             * tranquil i no la reclama mai.
             *
             * I MENTRE NO ES SAP, EL CARRO NO ES TOCA. Nomes es buida quan hi
             * ha un codi de comanda a la ma.
             */
            return fetch(API + '/api/public/comanda', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dades)
            }).then(function (r) {
                return r.json().catch(function () { return {}; }).then(function (cos) {
                    return { ok: r.ok, status: r.status, cos: cos || {} };
                });
            }).then(function (resposta) {
                if (!resposta.ok || !resposta.cos.ok || !resposta.cos.code) {
                    // El servidor pot tenir alguna cosa a dir (massa seguides, per exemple)
                    throw new Error(resposta.cos.error || String(resposta.status));
                }

                mostra(t.fet);
                linies = [];
                desa();
                oblidaClau();
                form.reset();
            }).catch(function (error) {
                /*
                 * El carro es queda tal com estava i el boto de WhatsApp
                 * segueix sent-hi, a sota: la comanda no es perd, nomes no ha
                 * anat per aqui.
                 */
                mostra((error && error.message && error.message.length > 3
                    ? error.message + ' '
                    : '') + t.falla);
                var wa = panell.querySelector('[data-carro-whatsapp]');
                if (wa) wa.classList.add('destacat');
            }).then(function () {
                boto.disabled = false;
            });
        }

        function pinta() {
            var compte = document.querySelector('[data-carro-compte]');
            var total = compta();
            if (compte) {
                compte.textContent = total || '';
                compte.hidden = !total;
            }
            document.querySelector('.carro-boto').hidden = total === 0 && panell.hidden;

            var caixa = panell.querySelector('[data-carro-linies]');
            if (!linies.length) {
                caixa.innerHTML = '<p class="buit">' + t.buit + '</p>';
            } else {
                caixa.innerHTML = linies.map(function (l) {
                    return '<div class="linia" data-linia="' + escapa(l.ref) + '">'
                        + '<div class="que"><span class="nom">' + escapa(l.nom) + '</span>'
                        + '<code>' + escapa(l.ref) + '</code></div>'
                        + '<div class="quants">'
                        + '<button type="button" data-menys aria-label="−">−</button>'
                        + '<span>' + l.qty + '</span>'
                        + '<button type="button" data-mes aria-label="+">+</button>'
                        + '<button type="button" data-treu aria-label="' + t.treu + '">&times;</button>'
                        + '</div></div>';
                }).join('');
            }
            panell.querySelector('[data-carro-whatsapp]').href = missatge();
        }

        function escapa(text) {
            return String(text).replace(/[&<>"']/g, function (c) {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
        }

        // --------------------------------------------------------- afegir-hi
        var botons = document.querySelectorAll('[data-carro-afegeix]');
        if (!botons.length && !linies.length) return;

        crea();
        pinta();

        botons.forEach(function (boto) {
            boto.addEventListener('click', function () {
                var ref = boto.dataset.ref;
                var linia = linies.filter(function (l) { return l.ref === ref; })[0];
                if (linia) linia.qty += 1;
                else {
                    /*
                     * El preu que ell veu, desat amb la linia.
                     * Nomes serveix per poder-li dir «ha canviat» quan la
                     * comanda arribi a l'ERP: alla el preu es torna a
                     * llegir del cataleg i aquest no es fa servir mai.
                     */
                    linies.push({
                        ref: ref,
                        nom: boto.dataset.nom,
                        qty: 1,
                        preu: Number(boto.dataset.preu) || null
                    });
                }
                desa();

                // Un senyal curt: s'ha afegit i el carro ja ho diu
                boto.classList.add('fet');
                window.setTimeout(function () { boto.classList.remove('fet'); }, 900);
            });
        });
    }

    /*
     * El desplegable d'una família.
     *
     * Una taula de cinc files amb quatre columnes no cap en un mòbil, i
     * comprant no es compara tot de cop: es tria el color que s'ha acabat.
     * En triar-lo canvien la foto, el preu, la disponibilitat, la
     * referència i els dos botons, que si no afegirien al carro el color
     * que hi havia abans.
     */
    function variants() {
        var tria = document.querySelector('[data-variants]');
        var caixa = document.querySelector('[data-familia]');
        if (!tria || !caixa) return;

        var gran = document.getElementById('foto-gran');
        var preu = caixa.querySelector('[data-preu-ref]');
        var abans = caixa.querySelector('[data-pvpr]');
        var estat = caixa.querySelector('[data-estat-ref]');
        var wa = caixa.querySelector('[data-wa]');
        var afegeix = caixa.querySelector('[data-carro-afegeix]');
        var refVista = caixa.querySelector('code[data-ref]');
        var eanLinia = caixa.querySelector('[data-ean-linia]');
        var eanVista = caixa.querySelector('code[data-ean]');

        function canvia() {
            var opcio = tria.options[tria.selectedIndex];
            if (!opcio) return;
            var d = opcio.dataset;
            var ref = opcio.value;

            if (gran && d.vFoto) {
                gran.src = d.vFoto;
                document.querySelectorAll('.mini[data-foto]').forEach(function (b) {
                    b.classList.toggle('actiu', b.dataset.foto === d.vFoto);
                });
            }

            if (preu) {
                preu.dataset.preuRef = ref;
                preu.querySelector('[data-preu]').textContent = diners(Number(d.vPreu));
                var sense = preu.querySelector('[data-preu-sense]');
                if (sense) sense.textContent = diners(Number(d.vSense));
            }
            if (abans) {
                abans.hidden = !d.vPvpr;
                if (d.vPvpr) abans.textContent = diners(Number(d.vPvpr));
            }
            if (estat) {
                estat.dataset.estatRef = ref;
                estat.textContent = estat.dataset[d.vEstat] || estat.dataset.unknown || '';
            }
            if (refVista) refVista.textContent = ref;
            // Una variant sense codi de barres no n'ensenya cap
            if (eanLinia) {
                eanLinia.hidden = !d.vEan;
                if (eanVista) eanVista.textContent = d.vEan || '';
            }

            if (wa) {
                wa.href = 'https://wa.me/34711550872?text=' + encodeURIComponent(
                    (document.documentElement.lang === 'es'
                        ? '¡Hola! Me interesa ' : 'Hola! M\'interessa ') + d.vNom + ' (' + ref + ')');
            }
            if (afegeix) {
                afegeix.dataset.ref = ref;
                afegeix.dataset.nom = d.vNom;
                afegeix.dataset.preu = d.vPreu;
            }

            // I si l'ERP ja ha contestat, el preu bo és el seu
            pintaPreus();
        }

        tria.addEventListener('change', canvia);
        canvia();
    }

    function engega() { preus(); galeria(); variants(); filtres(); carro(); }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', engega);
    else engega();
})();
