(() => {
  'use strict';

  const byId = id => document.getElementById(id);
  const joint = byId('joint');
  const target = byId('target');
  const range = byId('range');
  const preview = byId('frame');
  const cameraButtons = [...document.querySelectorAll('[data-camera]')];
  const readings = [...document.querySelectorAll('[data-reading]')];
  const clock = new Intl.DateTimeFormat(undefined, {hour: 'numeric', minute: '2-digit', second: '2-digit'});
  let camera = 'overview';
  let socket;
  let current;
  let pending;
  let frameHeader;
  let lastFrameAt = 0;
  let imageUrl;
  let retry;
  let closed = false;
  let eventId;

  function write(node, value) {
    if (node.textContent !== value) node.textContent = value;
  }

  function badge(id, state, label) {
    const node = byId(id);
    node.dataset.state = state;
    write(node, label);
  }

  function configureTarget() {
    const axis = current?.joints[joint.value];
    if (!axis) return;
    for (const input of [target, range]) {
      input.min = axis.min;
      input.max = axis.max;
      input.value = Math.round(axis.target);
    }
    write(byId('unit'), '(' + axis.unit + ')');
  }

  function online() {
    return socket?.readyState === WebSocket.OPEN && current && performance.now() - lastFrameAt < 5000;
  }

  function controls() {
    const live = Boolean(online());
    const busy = !live || Boolean(pending);
    byId('position-controls').disabled = busy;
    byId('hold').disabled = busy || current.motion !== 'moving';
    byId('home').disabled = busy;
    byId('lid').disabled = busy;
    byId('light').disabled = busy;
    for (const button of cameraButtons) button.disabled = !live;
    if (live) {
      badge('connection', 'live', 'Live');
      badge('motion', current.motion, {ready: 'Ready', moving: 'Moving', held: 'Held'}[current.motion]);
    } else {
      badge('connection', current ? 'disconnected' : 'waiting', current ? 'Disconnected' : 'Connecting');
      badge('motion', 'waiting', current ? 'State unavailable' : 'Waiting');
    }
  }

  function renderState(state, cameraId) {
    const newSession = !current || state.frame < current.frame;
    if (newSession || state.frame > current.frame || lastFrameAt === 0) lastFrameAt = performance.now();
    current = state;
    if (newSession) configureTarget();
    if (pending?.id && state.revision >= pending.id) {
      pending = undefined;
      write(byId('command-feedback'), '');
    }
    for (const node of readings) {
      const axis = state.joints[node.dataset.reading];
      const value = axis.unit === '°' ? axis.value + '°' : axis.value + ' ' + axis.unit;
      write(node, value);
    }
    write(byId('light-state'), state.inspection_light ? 'On' : 'Off');
    write(byId('light'), state.inspection_light ? 'Turn light off' : 'Turn light on');
    write(byId('lid'), state.joints.lid.target === state.joints.lid.min ? 'Close lid' : 'Open lid');
    const title = cameraId === 'overview' ? 'Overview' : 'Deck';
    write(byId('camera-label'), title);
    preview.alt = title + ' camera of the simulated workcell';
    write(byId('observed-at'), 'Observed ' + clock.format(new Date(state.observed_at)));
    for (const button of cameraButtons) button.setAttribute('aria-pressed', String(button.dataset.camera === cameraId));

    const recentId = state.recent_actions[0]?.id ?? 0;
    if (eventId !== recentId || newSession) {
      byId('activity-empty').hidden = state.recent_actions.length > 0;
      byId('events').replaceChildren(...state.recent_actions.map(action => {
        const row = document.createElement('li');
        const label = document.createElement('span');
        const time = document.createElement('time');
        label.textContent = action.label;
        time.dateTime = action.at;
        time.textContent = clock.format(new Date(action.at));
        row.append(label, time);
        return row;
      }));
      eventId = recentId;
    }
    controls();
  }

  function send(command) {
    if (!online() || pending) return;
    socket.send(JSON.stringify({command, revision: current.revision}));
    pending = {id: null, deadline: performance.now() + 5000};
    write(byId('command-feedback'), 'Applying control…');
    controls();
  }

  function receive(event) {
    if (typeof event.data === 'string') {
      const message = JSON.parse(event.data);
      if (message.type === 'frame') {
        frameHeader = message;
      } else if (message.type === 'accepted' && pending) {
        pending.id = message.id;
      } else if (message.type === 'rejected') {
        pending = undefined;
        write(byId('command-feedback'), message.message);
        controls();
      }
      return;
    }
    if (!frameHeader) return;
    const {state, camera: cameraId} = frameHeader;
    frameHeader = undefined;
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    imageUrl = URL.createObjectURL(event.data);
    preview.src = imageUrl;
    preview.hidden = false;
    byId('waiting').hidden = true;
    renderState(state, cameraId);
  }

  function reconnect() {
    clearTimeout(retry);
    if (!closed) retry = setTimeout(connect, 1200);
  }

  async function connect() {
    let key;
    try {
      const response = await fetch('./session.json', {cache: 'no-store', signal: AbortSignal.timeout(5000)});
      if (!response.ok) throw new Error('Workspace unavailable');
      ({key} = await response.json());
      if (typeof key !== 'string') throw new Error('Workspace unavailable');
    } catch {
      reconnect();
      return;
    }
    if (closed) return;
    const proxied = location.pathname.startsWith('/job-ui-proxy/');
    const url = new URL(proxied ? './ws/control' : './control', location.href);
    url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(url);
    const opening = setTimeout(() => socket.close(), 7000);
    socket.addEventListener('open', () => {
      socket.send(JSON.stringify({key}));
      if (camera !== 'overview') socket.send(JSON.stringify({camera}));
    });
    socket.addEventListener('message', event => {
      clearTimeout(opening);
      receive(event);
    });
    socket.addEventListener('close', () => {
      clearTimeout(opening);
      lastFrameAt = 0;
      frameHeader = undefined;
      if (pending) write(byId('command-feedback'), 'Connection interrupted. Check recent actions after reconnecting.');
      pending = undefined;
      controls();
      reconnect();
    });
  }

  joint.addEventListener('change', configureTarget);
  range.addEventListener('input', () => { target.value = range.value; });
  target.addEventListener('input', () => { range.value = target.value; });
  byId('move-form').addEventListener('submit', event => {
    event.preventDefault();
    send({action: 'move', joint: joint.value, target: target.valueAsNumber});
  });
  byId('hold').addEventListener('click', () => send({action: 'hold'}));
  byId('home').addEventListener('click', () => send({action: 'home'}));
  byId('lid').addEventListener('click', () => send({action: 'lid', enabled: current.joints.lid.target !== current.joints.lid.min}));
  byId('light').addEventListener('click', () => send({action: 'light', enabled: !current.inspection_light}));
  for (const button of cameraButtons) button.addEventListener('click', () => {
    camera = button.dataset.camera;
    socket.send(JSON.stringify({camera}));
  });
  window.addEventListener('pagehide', event => {
    if (event.persisted) return;
    closed = true;
    clearTimeout(retry);
    socket?.close();
    if (imageUrl) URL.revokeObjectURL(imageUrl);
  });
  setInterval(() => {
    if (pending && performance.now() >= pending.deadline) socket.close();
    if (socket?.readyState === WebSocket.OPEN && lastFrameAt && !online()) socket.close();
    controls();
  }, 300);
  connect();
})();
