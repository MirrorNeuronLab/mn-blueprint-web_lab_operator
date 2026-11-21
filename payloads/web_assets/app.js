(() => {
  'use strict';

  const byId = id => document.getElementById(id);
  const preview = byId('frame');
  const sampleControl = byId('sample-control');
  const wells = byId('sample-wells');
  const feedback = byId('feedback');
  const cameraButtons = [...document.querySelectorAll('[data-camera]')];
  const cameraNames = {overview: 'Overview', samples: 'Sample tray'};
  const clock = new Intl.DateTimeFormat(undefined, {hour: 'numeric', minute: '2-digit', second: '2-digit'});
  const checkLabels = {pending: 'Pending', passed: 'Match', needs_review: 'Review'};
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

  function online() {
    return socket?.readyState === WebSocket.OPEN && current && performance.now() - lastFrameAt < 5000;
  }

  function controls() {
    const live = Boolean(online());
    sampleControl.disabled = !live || Boolean(pending);
    for (const button of cameraButtons) button.disabled = !live;
    if (live) {
      badge('connection', 'live', 'Live');
    } else {
      badge('connection', current ? 'disconnected' : 'waiting', current ? 'Disconnected' : 'Connecting');
    }
  }

  function renderSample(sample) {
    const running = sample.status === 'running';
    const checking = sample.phase === 'checking' || sample.phase === 'complete';
    const labels = {running: 'Running', checking: 'Checking', passed: 'Passed', needs_review: 'Needs review', stopped: 'Stopped'};
    const state = sample.status === 'complete' ? sample.check.status : running && checking ? 'checking' : sample.status;
    badge('sample-status', state, labels[state]);
    write(byId('sample-action'), sample.action);
    write(sampleControl, running ? 'Stop sample' : 'Run sample again');
    sampleControl.classList.toggle('primary', !running);
    const progress = byId('sample-progress');
    progress.max = sample.total_transfers + sample.check.total;
    progress.value = sample.completed_transfers + sample.check.checked;
    const count = checking ? `${sample.check.checked} of ${sample.check.total} checked`
      : `${sample.completed_transfers} of ${sample.total_transfers} transfers`;
    write(byId('sample-count'), count);
    const criteria = byId('criteria');
    write(criteria, `Each vessel needs the expected fill and color within ${sample.check.tolerance_pp} percentage points.`);
    criteria.hidden = !checking;

    if (!wells.children.length) {
      for (const well of sample.wells) {
        const row = document.createElement('tr');
        const name = document.createElement('th');
        name.scope = 'row';
        name.textContent = well.name;
        row.append(name, ...['target', 'observed', 'check'].map(column => {
          const cell = document.createElement('td');
          cell.className = column;
          return cell;
        }));
        wells.append(row);
      }
    }
    sample.wells.forEach((well, index) => {
      const row = wells.children[index];
      row.style.setProperty('--dye', Math.min(100, well.concentration_percent) + '%');
      row.dataset.active = String(well.name === sample.reading_well);
      row.dataset.check = well.check;
      write(row.cells[1], well.target_percent + '%');
      write(row.cells[2], well.concentration_percent + '%');
      write(row.cells[3], checkLabels[well.check]);
      row.cells[3].title = well.issues.join('. ');
      row.cells[3].setAttribute('aria-label', [checkLabels[well.check], ...well.issues].join('. '));
    });
    byId('sample-results').hidden = false;
  }

  function renderState(state, cameraId) {
    const newSession = !current || state.frame < current.frame;
    if (newSession || state.frame > current.frame || lastFrameAt === 0) lastFrameAt = performance.now();
    current = state;
    if (pending?.id && state.revision >= pending.id) {
      pending = undefined;
      write(feedback, '');
    }
    const title = cameraNames[cameraId];
    write(byId('camera-label'), title);
    preview.alt = title + ' camera of the simulated workcell';
    write(byId('observed-at'), 'Observed ' + clock.format(new Date(state.observed_at)));
    for (const button of cameraButtons) button.setAttribute('aria-pressed', String(button.dataset.camera === cameraId));
    renderSample(state.sample);

    const recentId = state.recent_actions[0]?.id ?? 0;
    if (eventId !== recentId || newSession) {
      byId('activity').hidden = state.recent_actions.length === 0;
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

  function send(action) {
    if (!online() || pending) return;
    socket.send(JSON.stringify({command: {action}, revision: current.revision}));
    pending = {id: null, deadline: performance.now() + 5000};
    write(feedback, 'Applying control…');
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
        write(feedback, message.message);
        pending = undefined;
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
      if (pending) write(feedback, 'Connection interrupted. Check recent controls after reconnecting.');
      pending = undefined;
      controls();
      reconnect();
    });
  }

  sampleControl.addEventListener('click', () => send(current.sample.status === 'running' ? 'stop_sample' : 'restart_sample'));
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
