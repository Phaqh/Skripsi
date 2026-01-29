export function initState() {
  return {
    turn: 0,
    history: [],        // [{ player, opponent, payoff }]
    coopProbs: [],      // model predictions
    scores: {
      player: [],
      opponent: []
    }
  };
}
