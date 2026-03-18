var feedbackChart;
function updateChart(data){
  var ctx = document.getElementById('feedbackChart').getContext('2d');
  var labels = [];
  var averages = [];
  var counter = 1;  // Start labeling as Q1, Q2, etc.
  for(var key in data.question_averages){
    labels.push("Q" + counter);
    averages.push(data.question_averages[key].average);
    counter++;
  }
  if(feedbackChart){
    feedbackChart.destroy();
  }
  feedbackChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Average Rating',
        data: averages,
        backgroundColor: 'rgba(54, 162, 235, 0.6)'
      }]
    },
    options: {
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            stepSize: 1,
            max: 4
          }
        }
      }
    }
  });
}
