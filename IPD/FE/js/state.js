export function initState() {
  return {
    turn: 0,
    history: [],
    coopProbs: [],
    scores: {
      player: [],
      opponent: []
    },
    actions: {
      player: [0],
      opponent: [0]
    }
  };
}
