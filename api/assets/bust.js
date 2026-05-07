(function () {
    'use strict';

    function drawPlaceholder(canvas) {
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#272727';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    // ── 2D head: crops face from skin ────────────────────────────────────────

    function renderHead(canvas) {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            const W = canvas.clientWidth || canvas.width;
            const H = canvas.clientHeight || canvas.height;
            canvas.width = W;
            canvas.height = H;
            const ctx = canvas.getContext('2d');
            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(img, 8, 8, 8, 8, 0, 0, W, H);   // base face
            ctx.drawImage(img, 40, 8, 8, 8, 0, 0, W, H);  // hat layer
        };
        img.onerror = () => drawPlaceholder(canvas);
        img.src = canvas.dataset.skin;
    }

    // ── 3D bust via Three.js ──────────────────────────────────────────────────

    let threeReady = false;
    const threeQueue = [];

    function ensureThree(cb) {
        if (threeReady) { cb(); return; }
        threeQueue.push(cb);
        if (threeQueue.length > 1) return;
        const s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/three@0.158.0/build/three.min.js';
        s.onload = () => {
            threeReady = true;
            threeQueue.splice(0).forEach(f => f());
        };
        document.head.appendChild(s);
    }

    function renderBust(canvas) {
        ensureThree(() => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => buildBust(canvas, img);
            img.onerror = () => drawPlaceholder(canvas);
            img.src = canvas.dataset.skin;
        });
    }

    // BoxGeometry face order: +x,-x,+y,-y,+z,-z  (4 verts per face, TL/TR/BL/BR)
    // Minecraft UV: (0,0) = top-left, y down
    function setFaceUV(geo, face, x, y, w, h) {
        const uv = geo.attributes.uv;
        const b = face * 4;
        const u0 = x / 64, u1 = (x + w) / 64;
        const v1 = 1 - y / 64, v0 = 1 - (y + h) / 64;
        uv.setXY(b,     u0, v1);
        uv.setXY(b + 1, u1, v1);
        uv.setXY(b + 2, u0, v0);
        uv.setXY(b + 3, u1, v0);
        uv.needsUpdate = true;
    }

    function makeMesh(tex, w, h, d, faces) {
        const geo = new THREE.BoxGeometry(w, h, d);
        faces.forEach((f, i) => setFaceUV(geo, i, ...f));
        return new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ map: tex, transparent: true }));
    }

    function buildBust(canvas, skinImg) {
        // Match renderer to CSS display size
        const W = canvas.clientWidth  || canvas.width;
        const H = canvas.clientHeight || canvas.height;
        canvas.width  = W;
        canvas.height = H;

        const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false });
        renderer.setSize(W, H, false);
        renderer.setPixelRatio(window.devicePixelRatio || 1);

        const scene = new THREE.Scene();
        const cam = new THREE.PerspectiveCamera(40, W / H, 0.1, 100);

        // Slight 3/4 angle — orbit ~12° to the right around Y
        const orbitY = 0.21;
        const dist = 32;
        cam.position.set(Math.sin(orbitY) * dist, 8, Math.cos(orbitY) * dist);
        cam.lookAt(0, 2, 0);

        scene.add(new THREE.AmbientLight(0xffffff, 0.6));
        const sun = new THREE.DirectionalLight(0xffffff, 0.75);
        sun.position.set(6, 12, 8);
        scene.add(sun);

        const tex = new THREE.CanvasTexture(skinImg);
        tex.magFilter = THREE.NearestFilter;
        tex.minFilter = THREE.NearestFilter;

        const isNew = skinImg.height >= 64;

        // ── Head ──────────────────────────────────────────────────────────────
        const head = makeMesh(tex, 8, 8, 8, [
            [0,  8, 8, 8],
            [16, 8, 8, 8],
            [8,  0, 8, 8],
            [16, 0, 8, 8],
            [8,  8, 8, 8],
            [24, 8, 8, 8],
        ]);
        head.position.set(0, 10, 0);
        scene.add(head);

        // Hat (outer head layer)
        const hat = makeMesh(tex, 9, 9, 9, [
            [32, 8, 8, 8],
            [48, 8, 8, 8],
            [40, 0, 8, 8],
            [48, 0, 8, 8],
            [40, 8, 8, 8],
            [56, 8, 8, 8],
        ]);
        hat.position.set(0, 10, 0);
        hat.material.depthWrite = false;
        scene.add(hat);

        // ── Body ──────────────────────────────────────────────────────────────
        const body = makeMesh(tex, 8, 12, 4, [
            [16, 20, 4, 12],
            [28, 20, 4, 12],
            [20, 16, 8,  4],
            [28, 16, 8,  4],
            [20, 20, 8, 12],
            [32, 20, 8, 12],
        ]);
        body.position.set(0, 0, 0);
        scene.add(body);

        // ── Right arm (player's right = viewer's left, at -x) ─────────────────
        const rArm = makeMesh(tex, 4, 12, 4, [
            [48, 20, 4, 12],
            [40, 20, 4, 12],
            [44, 16, 4,  4],
            [48, 16, 4,  4],
            [44, 20, 4, 12],
            [52, 20, 4, 12],
        ]);
        rArm.position.set(-6, 0, 0);
        rArm.rotation.z = -0.18;  // splay outward
        rArm.rotation.x =  0.08;  // slight forward tilt
        scene.add(rArm);

        // ── Left arm (player's left = viewer's right, at +x) ──────────────────
        const lArmFaces = isNew ? [
            [40, 52, 4, 12],
            [32, 52, 4, 12],
            [36, 48, 4,  4],
            [40, 48, 4,  4],
            [36, 52, 4, 12],
            [44, 52, 4, 12],
        ] : [
            [40, 20, 4, 12],
            [48, 20, 4, 12],
            [44, 16, 4,  4],
            [48, 16, 4,  4],
            [44, 20, 4, 12],
            [52, 20, 4, 12],
        ];
        const lArm = makeMesh(tex, 4, 12, 4, lArmFaces);
        lArm.position.set(6, 0, 0);
        lArm.rotation.z =  0.18;  // splay outward
        lArm.rotation.x =  0.08;  // slight forward tilt
        scene.add(lArm);

        // ── Right leg (player's right = at -x) ────────────────────────────────
        const rLeg = makeMesh(tex, 4, 12, 4, [
            [8,  20, 4, 12],   // +x inner
            [0,  20, 4, 12],   // -x outer
            [4,  16, 4,  4],   // +y top
            [8,  16, 4,  4],   // -y bottom
            [4,  20, 4, 12],   // +z front
            [12, 20, 4, 12],   // -z back
        ]);
        rLeg.position.set(-2, -12, 0);
        rLeg.rotation.x = -0.08;  // slight backward lean
        scene.add(rLeg);

        // ── Left leg (player's left = at +x) ──────────────────────────────────
        const lLegFaces = isNew ? [
            [24, 52, 4, 12],   // +x outer
            [16, 52, 4, 12],   // -x inner
            [20, 48, 4,  4],   // +y top
            [24, 48, 4,  4],   // -y bottom
            [20, 52, 4, 12],   // +z front
            [28, 52, 4, 12],   // -z back
        ] : [
            [8,  20, 4, 12],
            [0,  20, 4, 12],
            [4,  16, 4,  4],
            [8,  16, 4,  4],
            [4,  20, 4, 12],
            [12, 20, 4, 12],
        ];
        const lLeg = makeMesh(tex, 4, 12, 4, lLegFaces);
        lLeg.position.set(2, -12, 0);
        lLeg.rotation.x = 0.08;  // slight forward lean
        scene.add(lLeg);

        // ── Render + resize ────────────────────────────────────────────────────
        function doRender() {
            const cW = canvas.clientWidth;
            const cH = canvas.clientHeight;
            if (cW && cH && (canvas.width !== cW || canvas.height !== cH)) {
                canvas.width  = cW;
                canvas.height = cH;
                renderer.setSize(cW, cH, false);
                cam.aspect = cW / cH;
                cam.updateProjectionMatrix();
            }
            renderer.render(scene, cam);
        }

        doRender();
        new ResizeObserver(doRender).observe(canvas);
    }

    // ── IntersectionObserver setup ────────────────────────────────────────────

    function init() {
        const opts = { rootMargin: '300px' };

        const io2 = new IntersectionObserver(entries => {
            entries.forEach(e => {
                if (!e.isIntersecting) return;
                io2.unobserve(e.target);
                renderHead(e.target);
            });
        }, opts);

        const io3 = new IntersectionObserver(entries => {
            entries.forEach(e => {
                if (!e.isIntersecting) return;
                io3.unobserve(e.target);
                renderBust(e.target);
            });
        }, opts);

        document.querySelectorAll('.head-canvas').forEach(c => io2.observe(c));
        document.querySelectorAll('.bust-canvas').forEach(c => io3.observe(c));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
