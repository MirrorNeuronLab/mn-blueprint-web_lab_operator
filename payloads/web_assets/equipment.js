/* Original workcell geometry. Scene units are for display only. */
const grid = Array.from({length: 96}, (_, index) => {
  const row = index % 8;
  const column = Math.floor(index / 8);
  return {name: `${'ABCDEFGH'[row]}${column + 1}`, x: (column - 5.5) * 0.272, z: (row - 3.5) * 0.272};
});
const wellNames = grid.map(site => site.name).sort((a, b) =>
  a[0].localeCompare(b[0]) || Number(a.slice(1)) - Number(b.slice(1)));

function createEquipment(scene) {
  const {BoxGeometry, CylinderGeometry, CircleGeometry, LatheGeometry, Group, Mesh,
    InstancedMesh, MeshStandardMaterial, Object3D, Vector2, Vector3} = LabThree;
  const surface = (color, roughness = 0.62, metalness = 0) =>
    new MeshStandardMaterial({color, roughness, metalness});
  const shell = surface(0xcbd6d2, 0.4);
  const frame = surface(0x334943, 0.52, 0.16);
  const edge = surface(0x617971);
  const steel = surface(0x9bafa8, 0.42, 0.35);
  const deck = surface(0x859d94, 0.64, 0.1);
  const plateColors = [0xf2eee3, 0xb4d4cf, 0xb9c9db, 0xd6ccba].map(color => surface(color));
  const rackColor = surface(0x435d58);
  const wellColor = surface(0x374b46);
  const liquidColor = surface(0x239e83, 0.32, 0.06);
  const tipColor = surface(0xe6ba6f, 0.4);
  const glow = new MeshStandardMaterial({color: 0x74c4ad, emissive: 0x419a80, emissiveIntensity: 0.55});
  const transform = new Object3D();

  function mesh(parent, geometry, material, x, y, z) {
    const part = new Mesh(geometry, material);
    part.position.set(x, y, z);
    parent.add(part);
    return part;
  }

  function box(parent, material, x, y, z, width, height, depth) {
    return mesh(parent, new BoxGeometry(width, height, depth), material, x, y, z);
  }

  function instance(part, index, x, y, z, height = 1) {
    transform.position.set(x, y, z);
    transform.scale.y = height;
    transform.updateMatrix();
    part.setMatrixAt(index, transform.matrix);
  }

  function gridMesh(parent, geometry, material, y) {
    const part = new InstancedMesh(geometry, material, grid.length);
    grid.forEach((site, i) => instance(part, i, site.x, y, site.z));
    parent.add(part);
    return part;
  }

  // Open chassis, two longitudinal tracks and one transverse gantry.
  for (const x of [-6.7, 6.7]) {
    box(scene, frame, x, 0.07, 0, 0.65, 0.27, 7.8);
    box(scene, shell, x, 0.82, 0, 0.77, 0.91, 8.9);
    box(scene, steel, x, 1.31, 0, 0.21, 0.10, 8.43);
    box(scene, frame, x, 1.38, 0, 0.09, 0.045, 8.50);
  }
  box(scene, frame, 0, 0.31, 0, 14.25, 0.48, 8.9);
  box(scene, shell, 0, 0.52, 0, 14.30, 0.23, 8.94);
  box(scene, deck, 0, 0.66, 0, 12.60, 0.09, 8.55);
  box(scene, frame, 0, 1.04, -4.2, 12.65, 0.72, 0.38);
  box(scene, edge, 0, 0.37, 4.47, 12.50, 0.10, 0.045);
  box(scene, glow, 6.7, 0.60, 4.49, 0.34, 0.055, 0.03);
  for (let x = -5.8; x < 6; x += 0.36) {
    box(scene, steel, x, 0.71, 3.90, 0.026, 0.018, 0.20);
  }

  const gantry = new Group();
  scene.add(gantry);
  for (const x of [-6.7, 6.7]) {
    box(gantry, frame, x, 1.57, 0, 0.67, 0.36, 0.96);
    box(gantry, shell, x, 2.45, 0, 0.49, 1.60, 0.67);
  }
  box(gantry, shell, 0, 3.13, 0, 13.55, 0.38, 0.63);
  box(gantry, frame, 0, 3.10, 0.34, 12.97, 0.23, 0.10);
  box(gantry, steel, 0, 3.12, 0.40, 12.75, 0.049, 0.035);
  const head = new Group();
  gantry.add(head);
  box(head, frame, 0, 2.97, 0.13, 0.99, 0.68, 0.99);
  box(head, shell, 0, 2.92, 0.49, 0.89, 0.62, 0.59);
  box(head, glow, 0, 3.02, 0.80, 0.37, 0.08, 0.028);

  const pipette = new Group();
  head.add(pipette);
  mesh(pipette, new CylinderGeometry(0.072, 0.072, 1.08, 16), steel, 0, 0.62, 0);
  mesh(pipette, new CylinderGeometry(0.205, 0.159, 0.34, 16), frame, 0, 0.06, 0);
  mesh(pipette, new CylinderGeometry(0.127, 0.083, 0.19, 16), steel, 0, -0.15, 0);
  const attachedTip = mesh(pipette, new CylinderGeometry(0.078, 0.022, 0.49, 14), tipColor, 0, -0.42, 0);
  attachedTip.visible = false;

  // Fixed labware positions leave the carriage visible when the deck is empty.
  const carrierSites = [[-1.67, -1.82], [2.39, -1.82], [-1.67, 1.22], [2.39, 1.22]];
  const rackSite = new Vector3(-4.90, 0, 0.98);
  const wasteSite = new Vector3(5.20, 1.07, 1.35);
  const park = new Vector3(5.33, 2.33, -2.88);
  const wellHeight = 0.98;
  const tipHeight = 1.27;
  const rim = new LatheGeometry([
    new Vector2(0.089, -0.055), new Vector2(0.089, 0.013),
    new Vector2(0.104, 0.025), new Vector2(0.118, 0.013), new Vector2(0.118, -0.020)
  ], 18);
  const cavity = new CircleGeometry(0.091, 18).rotateX(-Math.PI / 2);
  const liquid = new CylinderGeometry(0.085, 0.085, 1, 18);
  const plates = carrierSites.map(([x, z], index) => {
    box(scene, edge, x, 0.72, z, 3.44, 0.08, 2.34);
    const group = new Group();
    group.position.set(x, 0, z);
    group.visible = false;
    scene.add(group);
    const color = plateColors[index];
    box(group, color, 0, 0.80, 0, 3.33, 0.14, 2.31);
    box(group, color, 0, 0.894, 0, 3.26, 0.063, 2.24);
    gridMesh(group, rim, color, wellHeight - 0.022);
    const wells = gridMesh(group, cavity, wellColor, wellHeight - 0.038);
    const fill = new InstancedMesh(liquid, liquidColor, grid.length);
    fill.count = 0;
    fill.frustumCulled = false;
    group.add(fill);
    return {group, wells, fill, label: new Vector3(x, 0.83, z + 1.23), name: ''};
  });

  const rack = new Group();
  rack.position.copy(rackSite);
  rack.visible = false;
  scene.add(rack);
  box(rack, frame, 0, 0.77, 0, 3.24, 0.15, 2.19);
  box(rack, rackColor, 0, 0.91, 0, 3.23, 0.20, 2.17);
  gridMesh(rack, rim, steel, 1.023);
  gridMesh(rack, cavity, frame, 1.014);
  const tips = new InstancedMesh(new CylinderGeometry(0.062, 0.024, 0.29, 12), tipColor, grid.length);
  tips.frustumCulled = false;
  rack.add(tips);

  const waste = new Group();
  waste.position.set(wasteSite.x, 0, wasteSite.z);
  scene.add(waste);
  box(waste, frame, 0, 0.84, 0, 1.48, 0.29, 1.70);
  for (const x of [-0.68, 0.68]) box(waste, shell, x, 1.03, 0, 0.13, 0.19, 1.68);
  for (const z of [-0.77, 0.77]) box(waste, shell, 0, 1.03, z, 1.25, 0.19, 0.14);

  const wellSites = new Map();

  function show(names, state, capacity, tipAttached) {
    wellSites.clear();
    plates.forEach((plate, index) => {
      plate.name = names[index] ?? '';
      plate.group.visible = Boolean(plate.name);
      if (!plate.name) return;
      let filled = 0;
      grid.forEach(site => {
        const address = `${plate.name}/${site.name}`;
        wellSites.set(address, new Vector3(plate.group.position.x + site.x, wellHeight, plate.group.position.z + site.z));
        const fraction = state.wells[address].volume_ul / capacity;
        if (fraction <= 0) return;
        const height = 0.010 + Math.min(1, fraction) * 0.034;
        instance(plate.fill, filled++, site.x, wellHeight - 0.039 + height / 2, site.z, height);
      });
      plate.fill.count = filled;
      plate.fill.instanceMatrix.needsUpdate = true;
    });
    rack.visible = state.tips_remaining !== null;
    if (rack.visible) {
      tips.count = state.tips_remaining;
      grid.slice(grid.length - tips.count).forEach((site, index) => instance(tips, index, site.x, 1.13, site.z));
      tips.instanceMatrix.needsUpdate = true;
    }
    attachedTip.visible = tipAttached;
  }

  function focus(operation) {
    if (operation?.kind === 'pick_up_tip') {
      const site = grid[operation.tip_index];
      return {point: new Vector3(rackSite.x + site.x, tipHeight, rackSite.z + site.z), label: `Tip ${site.name}`};
    }
    if (operation?.kind === 'discard_tip') return {point: wasteSite, label: 'Waste'};
    const point = wellSites.get(operation?.well);
    return point ? {point, label: operation.well} : null;
  }

  function pose(point) {
    gantry.position.z = point.z;
    head.position.x = point.x;
    pipette.position.y = point.y;
  }

  pose(park);
  return {plates, wellSites, show, focus, pose, park,
    rackLabel: new Vector3(rackSite.x, 0.98, rackSite.z + 1.21),
    wasteLabel: new Vector3(wasteSite.x, 0.94, wasteSite.z + 0.92)};
}
