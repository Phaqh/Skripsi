import { initState } from './state.js';
import { bindUI } from './ui.js';
import { initPlots } from './viz.js';

let state = initState();

function reset() {
  state = initState();
  initPlots();
}

bindUI({ state, reset });
initPlots();
