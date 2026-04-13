import { stepGame, dummyOpponent } from './game.js';
import { updateStateView } from './ui_state.js';
import { updatePlots } from './viz.js';
import { updateActionPlot } from './viz.js';


export function bindUI({ getState, reset }) {

  document.getElementById('resetBtn').onclick = reset;

  document.getElementById('coopBtn').onclick = () => {
    doStep('C');
  };

  document.getElementById('defectBtn').onclick = () => {
    doStep('D');
  };

  function doStep(playerAction) {
    const state = getState(); // ✅ always get latest state

    console.log('STATE:', state);           // 👈 add this
    console.log('HISTORY:', state?.history); // 👈 and this

    console.log('BEFORE dummy:', state);

    const opponentAction = dummyOpponent(state.history);
    
    console.log('AFTER dummy:', state);
    stepGame(state, playerAction, opponentAction);

    updateStateView(state);
    updatePlots(state);
    updateActionPlot(state);
  }
}

export function dummyOpponent(history) {
  if (!history || history.length === 0) {
    return 'C'; // default behavior
  }

  const last = history[history.length - 1];
  return last.opponent || 'C';
}
