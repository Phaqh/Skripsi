export function initPlots() {
  Plotly.newPlot('coopProbPlot', [{
    y: [],
    mode: 'lines',
    name: 'P(Cooperate)'
  }], {
    title: 'Opponent Cooperation Probability'
  });

  Plotly.newPlot('scorePlot', [{
    y: [],
    mode: 'lines',
    name: 'Player Score'
  }], {
    title: 'Score Over Time'
  });
}

export function updatePlots(state) {
  Plotly.extendTraces('scorePlot', {
    y: [state.scores.player]
  }, [0]);
}
