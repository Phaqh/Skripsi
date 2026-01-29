export const PAYOFF = {
  C: { C: [3, 3], D: [0, 5] },
  D: { C: [5, 0], D: [1, 1] }
};

export function stepGame(state, playerAction, opponentAction) {
  const [pPayoff, oPayoff] =
    PAYOFF[playerAction][opponentAction];

  state.turn += 1;

  state.history.push({
    turn: state.turn,
    player: playerAction,
    opponent: opponentAction,
    payoff: [pPayoff, oPayoff]
  });

  state.scores.player.push(pPayoff);
  state.scores.opponent.push(oPayoff);

  return state;
}

export function dummyOpponent(history) {
  if (history.length === 0) return 'C';
  return history[history.length - 1].player;
}
