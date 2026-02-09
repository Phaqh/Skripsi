export const PAYOFF = {
  C: { C: [3, 3], D: [0, 5] },
  D: { C: [5, 0], D: [1, 1] }
};

export function stepGame(state, playerAction, opponentAction) {
  const [pPayoff, oPayoff] = PAYOFF[playerAction][opponentAction];

  state.turn += 1;

  state.history.push({
    turn: state.turn,
    player: playerAction,
    opponent: opponentAction,
    payoff: [pPayoff, oPayoff]
  });

    console.log(
    'TURN', state.turn,
    'prevP', state.actions.player.at(-1),
    'actionP', playerAction,
    'prevO', state.actions.opponent.at(-1),
    'actionO', opponentAction
  );
  
  state.scores.player.push(pPayoff);
  state.scores.opponent.push(oPayoff);

  // NEW: record actions numerically
  const pDelta = playerAction === 'C' ? 1 : -1;
  const oDelta = opponentAction === 'C' ? 1 : -1;

  state.actions.player.push(
    state.actions.player[state.actions.player.length - 1] + pDelta
  );

  state.actions.opponent.push(
    state.actions.opponent[state.actions.opponent.length - 1] + oDelta
  );

  return state;
}

export function dummyOpponent(history) {
  if (history.length === 0) return 'C';
  return history[history.length - 1].player;
}

