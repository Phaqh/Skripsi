import { stepGame, dummyOpponent } from './game.js';
import { updateStateView } from './ui_state.js';
import { updatePlots } from './viz.js';
import { updateActionPlot } from './viz.js';


export function bindUI({ state, reset }) {

  document.getElementById('resetBtn').onclick = reset;

  document.getElementById('coopBtn').onclick = () => {
    doStep('C');
  };

  document.getElementById('defectBtn').onclick = () => {
    doStep('D');
  };

  function doStep(playerAction) {
    const opponentAction = dummyOpponent(state.history);
    stepGame(state, playerAction, opponentAction);

    updateStateView(state);
    updatePlots(state);
    updateActionPlot(state);
  }
}
