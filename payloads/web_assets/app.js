(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const text = (id, value) => {
    const node = byId(id);
    if (node.textContent !== value) node.textContent = value;
  };
  const replayNode = byId('replay-data');
  const replay = replayNode ? JSON.parse(replayNode.textContent) : null;
  let index = 0;
  let timer = null;
  let currentView = null;
  const labels = {preparing:'Preparing',planning:'Planning',transitioning:'Preparing next phase',running:'Running',completed:'Completed',needs_review:'Needs review',failed:'Failed',cancelled:'Stopped'};
  const terminal = ['completed', 'needs_review', 'failed', 'cancelled'];
  const plate = byId('plate');
  const well = byId('well');
  let visiblePlates = [];
  const deck = mountDeck(selectWell, describeWell);

  well.replaceChildren(...wellNames.map(name => new Option(name)));
  plate.addEventListener('change', updateSelection);
  well.addEventListener('change', updateSelection);

  function describeWell(address) {
    const {volume_ul, liquids} = currentView.state.wells[address];
    return `${address}: ${volume_ul} µL · ${volume_ul > 0 ? liquids.join(', ') : 'empty'}`;
  }

  function updateSelection() {
    if (!plate.value) return;
    plate.title = plate.value;
    const address = `${plate.value}/${well.value}`;
    text('well-detail', describeWell(address));
    deck?.select(address);
  }

  function selectWell(address) {
    [plate.value, well.value] = address.split('/');
    updateSelection();
  }

  function renderState(view) {
    currentView = view;
    text('status', labels[view.status] || 'Preparing');
    byId('reason').hidden = !terminal.includes(view.status) || !view.reason;
    text('reason', view.reason || '');
    byId('tip-count').hidden = view.state.tips_remaining === null;
    text('tip-count', view.state.tips_remaining === null ? '' : `${view.state.tips_remaining} unused tips`);
    text('progress', ['preparing', 'planning', 'transitioning'].includes(view.status) ? '' :
      `${view.steps_completed} / ${view.steps_total ?? replay?.result.steps_total ?? 0}`);
    byId('operation').hidden = !view.operation;
    text('current-step', view.current_step?.replaceAll('_', ' ') || '');
    byId('current-step').title = byId('current-step').textContent;
    text('operation-label', view.operation?.label || '');
    if (view.plates.length !== visiblePlates.length
        || view.plates.some((name, i) => name !== visiblePlates[i])) {
      const selectedPlate = plate.value;
      visiblePlates = view.plates;
      plate.replaceChildren(...visiblePlates.map(name => new Option(name)));
      if (visiblePlates.includes(selectedPlate)) plate.value = selectedPlate;
    }
    byId('well-inspector').hidden = visiblePlates.length === 0;
    deck?.show(view);
    updateSelection();
    const events = byId('events');
    events.replaceChildren();
    byId('empty').hidden = view.events.length > 0 || Boolean(view.operation) || terminal.includes(view.status);
    for (const event of [...view.events].reverse()) {
      const row = document.createElement('li');
      row.className = event.decision === 'warning' ? 'warning' : event.decision === 'needs_review' ? 'needs_review' : '';
      const name = document.createElement('span');
      name.className = 'step'; name.textContent = event.decision === 'warning' ? 'Risk' : event.decision === 'needs_review' ? 'Needs review' : event.step.replaceAll('_', ' ');
      name.title = name.textContent;
      name.setAttribute('aria-label', `${name.textContent}: ${event.step.replaceAll('_', ' ')}`);
      const reason = document.createElement('span');
      reason.className = 'reason'; reason.textContent = event.reason;
      row.append(name, reason); events.append(row);
    }
  }

  function frame() {
    const frames = replay.frames.slice(0, index);
    const last = frames.at(-1);
    const done = index === replay.frames.length;
    renderState({status: done ? replay.result.status : 'running',
      reason: done ? replay.result.reason : '',
      steps_completed: frames.filter(value => value.passed).length,
      plates: replay.plates, well_capacity_ul: replay.well_capacity_ul,
      state: last ? last.after : replay.initial,
      events: frames.flatMap(value => value.rows)});
    byId('frame').value = String(index);
    text('position', `${index} / ${replay.frames.length}`);
    byId('previous').disabled = index === 0;
    byId('next').disabled = done;
  }

  function pause() { if (timer) clearInterval(timer); timer = null; text('play', 'Play'); }
  if (replay) {
    byId('saved-assessment').hidden = false;
    text('assessment-outcome', replay.result.summary || 'The simulation ended without a saved summary.');
    text('assessment-evidence', `${replay.frames.length} recorded events in trace.json. Compare the replay with the saved plan and report.md. Values come from simulation bookkeeping.`);
    byId('replay').hidden = false;
    byId('frame').max = String(replay.frames.length);
    byId('play').disabled = replay.frames.length === 0;
    byId('previous').onclick = () => { pause(); index = Math.max(0, index - 1); frame(); };
    byId('next').onclick = () => { pause(); index = Math.min(replay.frames.length, index + 1); frame(); };
    byId('frame').oninput = event => { pause(); index = Number(event.target.value); frame(); };
    byId('play').onclick = () => {
      if (timer) { pause(); return; }
      if (index === replay.frames.length) index = 0;
      text('play', 'Pause'); frame();
      timer = setInterval(() => {
        index++;
        frame();
        if (index === replay.frames.length) pause();
      }, 850);
    };
    frame();
  } else {
    function connect() {
      const url = new URL(window.__MN_JOB_UI_PROXY_BASE__ ? 'ws/monitor/ws' : 'monitor/ws', location.href);
      url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = new WebSocket(url);
      socket.onmessage = event => {
        renderState(JSON.parse(event.data));
        byId('connection').hidden = true;
      };
      socket.onclose = () => {
        if (currentView && (currentView.status === 'transitioning' || terminal.includes(currentView.status))) return;
        byId('connection').hidden = false;
        setTimeout(connect, 1000);
      };
    }
    connect();
  }
})();
