console.log('viz.js loading');

export function initPlots() {

  Plotly.newPlot('scorePlot', [{
    y: [],
    mode: 'lines+markers',
    name: 'Player Score'
  }], {
    title: 'Score Over Time'
  });

  Plotly.newPlot('actionPlot', [
  {
    y: [0],
    mode: 'lines+markers',
    name: 'Agent',
    line: { width: 3 },
    marker: { size: 6 }
  },
  {
    y: [0],
    mode: 'lines+markers',
    name: 'Opponent',
    line: { width: 1, dash: 'dot' },
    marker: { size: 4 }
  }
  ], {
    title: 'Cumulative Action Trajectory',
    xaxis: { title: 'Turn' },
    yaxis: {
      title: 'Cumulative Cooperation Level',
      zeroline: true,
      // autorange: true,
      zerolinewidth: 2
    }
  });


}

export function updatePlots(state) {
  const lastScore = state.scores.player[state.scores.player.length - 1];

  Plotly.extendTraces('scorePlot', {
    y: [[lastScore]]
  }, [0]);
}


export function updateActionPlot(state) {
  const p = state.actions.player[state.actions.player.length - 1];
  const o = state.actions.opponent[state.actions.opponent.length - 1];

  Plotly.extendTraces(
    'actionPlot',
    { y: [[p], [o]] },
    [0, 1]
  );
    Plotly.relayout('actionPlot', {
    'yaxis.autorange': true
  });
}


console.log('viz.js loaded');