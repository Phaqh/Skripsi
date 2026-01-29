export function updateStateView(state) {
  document.getElementById('turnInfo').innerText =
    `Turn: ${state.turn}`;

  if (state.history.length > 0) {
    const last = state.history[state.history.length - 1];
    document.getElementById('payoffInfo').innerText =
      `Last move: You=${last.player}, Opponent=${last.opponent}
       Payoff: You=${last.payoff[0]}, Opponent=${last.payoff[1]}`;
  }
}
