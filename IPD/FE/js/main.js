import { initState } from './state.js';
import { bindUI } from './ui.js';
import { initPlots } from './viz.js';

let state = initState();

function reset() {
  const newState = initState();

  Object.keys(newState).forEach(key => {
    state[key] = newState[key];
  });

  initPlots();
}

bindUI({ 
  getState: () => state,
  reset
});

initPlots();
