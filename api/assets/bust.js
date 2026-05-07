(function () {
    'use strict';

    function drawPlaceholder(canvas) {
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#272727';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    // ── 2D head: just crops the face from the skin ────────────────────────────

    function renderHead(canvas) {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            const ctx = canvas.getContext('2d');
            ctx.imageSmoothingEnabled = false;
            const s = canvas.width;
            ctx.drawImage(img, 8, 8, 8, 8, 0, 0, s, s);   // base face
            ctx.drawImage(img, 40, 8, 8, 8, 0, 0, s, s);  // outer (hat) layer
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

    // BoxGeometry face order: +x, -x, +y, -y, +z, -z  (4 verts per face)
    // Minecraft skin coords: (0,0) = top-left, y increases downward
    function setFaceUV(geo, face, x, y, w, h) {
        const uv = geo.attributes.uv;
        const b = face * 4;
        const u0 = x / 64, u1 = (x + w) / 64;
        const v1 = 1 - y / 64, v0 = 1 - (y + h) / 64;
        uv.setXY(b,     u0, v1);  // TL
        uv.setXY(b + 1, u1, v1);  // TR
        uv.setXY(b + 2, u0, v0);  // BL
        uv.setXY(b + 3, u1, v0);  // BR
        uv.needsUpdate = true;
    }

    // faces: [[x,y,w,h] × 6]  order: +x,-x,+y,-y,+z,-z
    function makeMesh(tex, w, h, d, faces) {
        const geo = new THREE.BoxGeometry(w, h, d);
        faces.forEach((f, i) => setFaceUV(geo, i, ...f));
        return new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ map: tex, transparent: true }));
    }

    function buildBust(canvas, skinImg) {
        const W = canvas.width, H = canvas.height;
        const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false });
        renderer.setSize(W, H);
        renderer.setPixelRatio(1);

        const scene = new THREE.Scene();
        const cam = new THREE.PerspectiveCamera(38, W / H, 0.1, 100);
        cam.position.set(0, 10, 30);
        cam.lookAt(0, 4, 0);

        scene.add(new THREE.AmbientLight(0xffffff, 0.65));
        const sun = new THREE.DirectionalLight(0xffffff, 0.7);
        sun.position.set(5, 10, 8);
        scene.add(sun);

        const tex = new THREE.CanvasTexture(skinImg);
        tex.magFilter = THREE.NearestFilter;
        tex.minFilter = THREE.NearestFilter;

        const isNew = skinImg.height >= 64;

        // Head (base layer)
        const head = makeMesh(tex, 8, 8, 8, [
            [0,  8, 8, 8],   // +x right
            [16, 8, 8, 8],   // -x left
            [8,  0, 8, 8],   // +y top
            [16, 0, 8, 8],   // -y bottom
            [8,  8, 8, 8],   // +z front
            [24, 8, 8, 8],   // -z back
        ]);
        head.position.set(0, 10, 0);
        scene.add(head);

        // Hat / outer head layer
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

        // Body
        const body = makeMesh(tex, 8, 12, 4, [
            [16, 20, 4, 12],  // +x right
            [28, 20, 4, 12],  // -x left
            [20, 16, 8,  4],  // +y top
            [28, 16, 8,  4],  // -y bottom
            [20, 20, 8, 12],  // +z front
            [32, 20, 8, 12],  // -z back
        ]);
        body.position.set(0, 0, 0);
        scene.add(body);

        // Right arm (player's right = viewer's left = at -x)
        const rArm = makeMesh(tex, 4, 12, 4, [
            [48, 20, 4, 12],  // +x inner
            [40, 20, 4, 12],  // -x outer
            [44, 16, 4,  4],  // +y top
            [48, 16, 4,  4],  // -y bottom
            [44, 20, 4, 12],  // +z front
            [52, 20, 4, 12],  // -z back
        ]);
        rArm.position.set(-6, 0, 0);
        scene.add(rArm);

        // Left arm (player's left = viewer's right = at +x)
        const lArmFaces = isNew ? [
            [40, 52, 4, 12],  // +x outer
            [32, 52, 4, 12],  // -x inner
            [36, 48, 4,  4],  // +y top
            [40, 48, 4,  4],  // -y bottom
            [36, 52, 4, 12],  // +z front
            [44, 52, 4, 12],  // -z back
        ] : [
            // Mirror right arm for old 64x32 skins
            [40, 20, 4, 12],
            [48, 20, 4, 12],
            [44, 16, 4,  4],
            [48, 16, 4,  4],
            [44, 20, 4, 12],
            [52, 20, 4, 12],
        ];
        const lArm = makeMesh(tex, 4, 12, 4, lArmFaces);
        lArm.position.set(6, 0, 0);
        scene.add(lArm);

        renderer.render(scene, cam);
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
