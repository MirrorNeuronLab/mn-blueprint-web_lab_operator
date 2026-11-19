# Simulation and viewer dependencies

The worker installs [PyLabRobot 0.2.1](https://github.com/PyLabRobot/pylabrobot)
under its MIT license. The 3D workcell uses the Chatterbox simulation's tracked
state.

`web_assets/vendor/three.min.js` bundles the WebGL renderer and OrbitControls
from [Three.js r186](https://github.com/mrdoob/three.js/releases/tag/r186).
`web_assets/vendor/three.LICENSE.txt` carries the MIT license from the npm
distribution. The live page serves the bundle on the Job UI origin. The
standalone replay embeds the same bundle and license.

To reproduce the bundle, run these commands in an empty temporary directory.

```sh
npm install --save-exact three@0.186.0 esbuild@0.25.12
cat > three.entry.js <<'EOF'
export {
  BoxGeometry, CircleGeometry, CylinderGeometry, DirectionalLight, Group, HemisphereLight,
  InstancedMesh, LatheGeometry, Mesh, MeshBasicMaterial, MeshStandardMaterial, Object3D,
  OrthographicCamera, Raycaster, Scene, TorusGeometry, Vector2, Vector3, WebGLRenderer
} from 'three';
export {OrbitControls} from 'three/addons/controls/OrbitControls.js';
EOF
./node_modules/.bin/esbuild three.entry.js \
  --bundle --minify --format=iife --global-name=LabThree --legal-comments=inline \
  '--banner:js=/*! Three.js r186 and OrbitControls | MIT | see three.LICENSE.txt */' \
  --outfile=three.min.js
```

Copy the bundle into `web_assets/vendor/` and save `node_modules/three/LICENSE`
there as `three.LICENSE.txt`.
The SHA-256 of the pinned bundle is
`8a4e07634ae83fc13924a8e383f67fcc97e89d0207fcd9357c248e1e7c2e7ea1`.
