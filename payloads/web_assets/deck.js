/* Render tracker snapshots and keep the camera and well inspection browser-local. */
function mountDeck(selectWell, describeWell) {
  const {DirectionalLight, HemisphereLight, Mesh, MeshBasicMaterial, OrbitControls, OrthographicCamera,
    Raycaster, Scene, TorusGeometry, Vector2, Vector3, WebGLRenderer} = LabThree;
  const canvas = document.getElementById('deck');
  const viewport = canvas.parentElement;
  const labels = document.getElementById('deck-labels');
  const targetLabel = document.getElementById('deck-target');
  const help = document.getElementById('deck-help');
  const tools = document.getElementById('deck-tools');
  const unavailable = document.getElementById('deck-unavailable');

  function available(value) {
    canvas.hidden = labels.hidden = help.hidden = tools.hidden = !value;
    unavailable.hidden = value;
  }

  const context = canvas.getContext('webgl2', {alpha: true, antialias: true});
  if (!context) {
    available(false);
    return null;
  }
  const renderer = new WebGLRenderer({canvas, context, alpha: true, antialias: true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const scene = new Scene();
  const camera = new OrthographicCamera(-10, 10, 6, -6, 0.1, 100);
  camera.position.set(7.4, 11.6, 16);
  const controls = new OrbitControls(camera, canvas);
  controls.target.set(0, 1.15, -0.15);
  controls.minPolarAngle = 0.16;
  controls.maxPolarAngle = 1.29;
  controls.minZoom = 0.7;
  controls.maxZoom = 4.5;
  controls.update();
  controls.saveState();

  scene.add(new HemisphereLight(0xffffff, 0x85918c, 2.05));
  const key = new DirectionalLight(0xfffaf0, 2.0);
  key.position.set(-4, 8, 5);
  scene.add(key);
  const rim = new DirectionalLight(0xd6ede6, 1.15);
  rim.position.set(6, 4, -5);
  scene.add(rim);
  const equipment = createEquipment(scene);

  function marker(radius, color) {
    const part = new Mesh(new TorusGeometry(radius, 0.019, 8, 36),
      new MeshBasicMaterial({color, depthTest: false}));
    part.rotation.x = -Math.PI / 2;
    part.visible = false;
    part.renderOrder = 1;
    scene.add(part);
    return part;
  }

  const selectedMarker = marker(0.14, 0x117464);
  const activeMarker = marker(0.191, 0xcf660d);
  activeMarker.renderOrder = 2;

  function makeLabel(value) {
    const label = document.createElement('span');
    label.className = 'lab-label';
    label.textContent = value;
    label.hidden = true;
    labels.append(label);
    return label;
  }

  const plateLabels = equipment.plates.map(() => makeLabel(''));
  const rackLabel = makeLabel('Tips');
  const wasteLabel = makeLabel('Waste');
  const screenPoint = new Vector3();
  const liftedLabel = new Vector3();
  const head = equipment.park.clone();
  const destination = equipment.park.clone();
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let active = null;
  let rackPresent = false;
  let motion = null;
  let frame = 0;

  function positionLabel(label, point) {
    if (point) screenPoint.copy(point).project(camera);
    label.hidden = !point || Math.abs(screenPoint.x) > 0.92 || Math.abs(screenPoint.y) > 0.93;
    if (label.hidden) return;
    label.style.left = `${(screenPoint.x + 1) * 50}%`;
    label.style.top = `${(1 - screenPoint.y) * 50}%`;
  }

  function draw(now) {
    frame = 0;
    if (motion) {
      const elapsed = Math.max(0, Math.min(1, (now - motion.start) / 260));
      const travel = Math.max(0, Math.min(1, (elapsed - 0.18) / 0.56));
      head.lerpVectors(motion.from, destination, travel * travel * (3 - 2 * travel));
      const raised = Math.max(motion.from.y, destination.y, 2.23);
      head.y = elapsed < 0.74
        ? motion.from.y + (raised - motion.from.y) * Math.min(1, elapsed / 0.18)
        : raised + (destination.y - raised) * ((elapsed - 0.74) / 0.26);
      equipment.pose(head);
      if (elapsed < 1) invalidate();
      else motion = null;
    }
    renderer.render(scene, camera);
    equipment.plates.forEach((plate, index) => {
      plateLabels[index].textContent = plate.name;
      positionLabel(plateLabels[index], plate.name ? plate.label : null);
    });
    positionLabel(rackLabel, rackPresent ? equipment.rackLabel : null);
    positionLabel(wasteLabel, rackPresent ? equipment.wasteLabel : null);
    if (active) {
      liftedLabel.copy(active.point);
      liftedLabel.y += 0.38;
      targetLabel.textContent = active.label;
    }
    positionLabel(targetLabel, active ? liftedLabel : null);
  }

  function invalidate() {
    if (!frame && !canvas.hidden) frame = requestAnimationFrame(draw);
  }

  function resize() {
    const {clientWidth: width, clientHeight: height} = canvas;
    if (!width || !height) return;
    const aspect = width / height;
    const span = Math.max(5.0, 9.0 / aspect);
    camera.left = -span * aspect;
    camera.right = span * aspect;
    camera.top = span;
    camera.bottom = -span;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    invalidate();
  }

  controls.addEventListener('change', invalidate);
  available(true);
  new ResizeObserver(resize).observe(viewport);
  resize();
  canvas.addEventListener('webglcontextlost', () => {
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    available(false);
  });
  canvas.addEventListener('webglcontextrestored', () => {
    available(true);
    resize();
  });

  const zoomIn = () => controls.dollyIn(0.8);
  const zoomOut = () => controls.dollyOut(0.8);
  document.getElementById('zoom-in').onclick = zoomIn;
  document.getElementById('zoom-out').onclick = zoomOut;
  document.getElementById('fit-deck').onclick = () => controls.reset();
  const keys = {
    ArrowLeft: () => controls.rotateLeft(0.14),
    ArrowRight: () => controls.rotateLeft(-0.14),
    ArrowUp: () => controls.rotateUp(0.14),
    ArrowDown: () => controls.rotateUp(-0.14),
    '+': zoomIn,
    '-': zoomOut,
    Home: () => controls.reset(),
  };
  canvas.addEventListener('keydown', event => {
    if (!Object.hasOwn(keys, event.key)) return;
    event.preventDefault();
    keys[event.key]();
  });

  const ray = new Raycaster();
  const cursor = new Vector2();
  let pressed = null;

  function wellAt(event) {
    const rect = canvas.getBoundingClientRect();
    cursor.set((event.clientX - rect.left) * 2 / rect.width - 1,
      1 - (event.clientY - rect.top) * 2 / rect.height);
    ray.setFromCamera(cursor, camera);
    const plates = equipment.plates.filter(plate => plate.name);
    const [hit] = ray.intersectObjects(plates.map(plate => plate.wells), false);
    if (!hit) return '';
    const plate = plates.find(plate => plate.wells === hit.object);
    return `${plate.name}/${grid[hit.instanceId].name}`;
  }

  canvas.addEventListener('pointerdown', event => {
    pressed = event.isPrimary && event.button === 0 ? event : null;
  });
  canvas.addEventListener('pointercancel', () => { pressed = null; });
  canvas.addEventListener('pointermove', event => {
    if (!event.buttons) {
      const well = wellAt(event);
      canvas.title = well ? describeWell(well) : '';
    }
  });
  canvas.addEventListener('pointerup', event => {
    if (pressed?.pointerId === event.pointerId
        && Math.hypot(event.clientX - pressed.clientX, event.clientY - pressed.clientY) < 5) {
      const well = wellAt(event);
      if (well) selectWell(well);
    }
    pressed = null;
  });

  function select(address) {
    const point = equipment.wellSites.get(address);
    selectedMarker.visible = Boolean(point) && address !== active?.label;
    if (point) selectedMarker.position.copy(point);
    invalidate();
  }

  function show(view) {
    equipment.show(view.plates, view.state, view.well_capacity_ul, Boolean(view.tip_attached));
    rackPresent = view.state.tips_remaining !== null;
    active = equipment.focus(view.operation);
    activeMarker.visible = Boolean(active);
    if (active) activeMarker.position.copy(active.point);

    const kind = view.operation?.kind;
    const next = active && kind !== 'check_volume' ? active.point.clone() : equipment.park;
    if (next !== equipment.park) next.y += kind === 'aspirate' ? 0.55 : 0.68;
    if (!destination.equals(next)) {
      destination.copy(next);
      if (reducedMotion.matches) {
        motion = null;
        head.copy(destination);
        equipment.pose(head);
      } else {
        motion = {from: head.clone(), start: performance.now()};
      }
    }
    invalidate();
  }

  return {show, select};
}
