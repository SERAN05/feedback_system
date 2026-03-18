// AI Sentiment Analysis workflow
document.addEventListener('DOMContentLoaded', function() {
  const aiSentimentBtn = document.getElementById('aiSentimentBtn');
  const downloadSentimentPdfBtn = document.getElementById('downloadSentimentPdfBtn');
  if (aiSentimentBtn && downloadSentimentPdfBtn) {
    aiSentimentBtn.addEventListener('click', function() {
      aiSentimentBtn.disabled = true;
      aiSentimentBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Analyzing...';
      // Call backend to run sentiment analysis (dummy endpoint, can reuse PDF endpoint for now)
      fetch('/admin/api/download-sentiment-pdf', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (typeof getCookie === 'function' ? getCookie('csrf_token') : '')
        },
        body: JSON.stringify({ category: window.category_filter || 'all' })
      })
      .then(res => {
        if (!res.ok) throw new Error('Analysis failed');
        // Show download button
        downloadSentimentPdfBtn.style.display = 'inline-block';
        aiSentimentBtn.innerHTML = '<i class="fas fa-brain me-2"></i>AI Sentiment Analysis';
        aiSentimentBtn.disabled = false;
      })
      .catch(() => {
        aiSentimentBtn.innerHTML = '<i class="fas fa-brain me-2"></i>AI Sentiment Analysis';
        aiSentimentBtn.disabled = false;
        alert('Sentiment analysis failed.');
      });
    });
    // Download PDF button logic (already present)
    downloadSentimentPdfBtn.addEventListener('click', function() {
      downloadSentimentPdfBtn.disabled = true;
      fetch('/admin/api/download-sentiment-pdf', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': (typeof getCookie === 'function' ? getCookie('csrf_token') : '')
        },
        body: JSON.stringify({ category: window.category_filter || 'all' })
      })
      .then(res => res.blob())
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Sentiment_Report_${window.category_filter || 'all'}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        downloadSentimentPdfBtn.disabled = false;
      })
      .catch(() => {
        alert('Error generating sentiment report PDF.');
        downloadSentimentPdfBtn.disabled = false;
      });
    });
  }
});

// Sentiment PDF download
const downloadSentimentBtn = document.getElementById('downloadSentimentPdfBtn');
if (downloadSentimentBtn) {
  downloadSentimentBtn.addEventListener('click', function() {
    const category = window.category_filter || 'all';
    downloadSentimentBtn.disabled = true;
    fetch('/admin/api/download-sentiment-pdf', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': (typeof getCookie === 'function' ? getCookie('csrf_token') : '')
      },
      body: JSON.stringify({ category })
    })
    .then(res => res.blob())
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Sentiment_Report_${category}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      downloadSentimentBtn.disabled = false;
    })
    .catch(() => {
      alert('Error generating sentiment report PDF.');
      downloadSentimentBtn.disabled = false;
    });
  });
}

document.addEventListener('DOMContentLoaded', function(){
  console.log("Admin JS loaded");
  var isOpenToAll = document.getElementById('is_open_to_all');
  var startRoll = document.getElementById('start_roll_number');
  var endRoll = document.getElementById('end_roll_number');
  var rollRangeFields = document.getElementById('roll-range-fields');
  // --- GLOBAL ARRAYS FOR ROLL NUMBERS ---
  let specificRolls = [];
  let fileRolls = [];

  // --- DOM ELEMENTS ---
  const specificInput = document.getElementById('specific_roll_input');
  const addSpecificBtn = document.getElementById('add_specific_roll_btn');
  const specificList = document.getElementById('specific_roll_list');
  const fileInput = document.getElementById('roll_file_input');
  const fileRollList = document.getElementById('file_roll_list');
  const allocatedDiv = document.getElementById('allocated_roll_numbers');

  function setDisabledState() {
    if (!isOpenToAll || !startRoll || !endRoll) {
      console.log('One or more elements not found:', {isOpenToAll, startRoll, endRoll});
      return;
    }
    var disabled = isOpenToAll.checked;
    // Disable/enable roll number range fields
    startRoll.disabled = disabled;
    endRoll.disabled = disabled;
    startRoll.readOnly = disabled;
    endRoll.readOnly = disabled;
    // Disable/enable specific roll and file upload fields
    if (specificInput) specificInput.disabled = disabled;
    if (addSpecificBtn) addSpecificBtn.disabled = disabled;
    if (fileInput) fileInput.disabled = disabled;
    if (disabled) {
      startRoll.classList.add('bg-light');
      endRoll.classList.add('bg-light');
      // Clear all roll number data and UI
      specificRolls.length = 0;
      fileRolls.length = 0;
      if (specificInput) specificInput.value = '';
      if (fileInput) fileInput.value = '';
      updateSpecificList();
      updateFileRollList();
      // Clear allocated roll numbers section
      if (allocatedDiv) allocatedDiv.innerHTML = '<span class="text-muted">No roll numbers allocated yet.</span>';
      console.log('TOGGLE ON: All roll number fields disabled, all roll numbers cleared, allocated section cleared');
    } else {
      startRoll.classList.remove('bg-light');
      endRoll.classList.remove('bg-light');
      updateAllocatedRollNumbers();
      console.log('TOGGLE OFF: All roll number fields enabled');
    }
  }
  if (isOpenToAll) {
    isOpenToAll.addEventListener('change', setDisabledState);
    setDisabledState(); // Initial state
  } else {
    console.log('Toggle not found');
  }
  // Extra: force update on page show (for bfcache)
  window.addEventListener('pageshow', setDisabledState);

  // --- Specific Roll Numbers Logic ---
  function updateSpecificList() {
    if (!specificList) return;
    specificList.innerHTML = specificRolls.map((roll, idx) =>
      `<span class='badge bg-secondary me-1 mb-1'>${roll} <button type='button' class='btn btn-sm btn-danger btn-remove-roll' data-idx='${idx}'>&times;</button></span>`
    ).join('');
    console.log('Specific roll list updated:', specificRolls);
  }
  if (addSpecificBtn && specificInput) {
    addSpecificBtn.addEventListener('click', function() {
      if (addSpecificBtn.disabled) {
        alert('Add button is disabled. Make sure Open to All Students is OFF.');
        return;
      }
      const val = specificInput.value.trim();
      if (!val) {
        alert('Please enter a roll number before adding.');
        return;
      }
      if (!specificRolls.includes(val)) {
        specificRolls.push(val);
        updateSpecificList();
        specificInput.value = '';
        updateAllocatedRollNumbers();
        console.log('Added specific roll:', val);
      } else {
        alert('This roll number is already added.');
      }
    });
    specificInput.addEventListener('keyup', function(e) {
      if (e.key === 'Enter' && !addSpecificBtn.disabled) {
        addSpecificBtn.click();
      }
    });
    if (specificList) {
      specificList.addEventListener('click', function(e) {
        if (e.target.classList.contains('btn-remove-roll')) {
          const idx = parseInt(e.target.getAttribute('data-idx'));
          specificRolls.splice(idx, 1);
          updateSpecificList();
          updateAllocatedRollNumbers();
          console.log('Removed specific roll at idx:', idx);
        }
      });
    }
  }

  // --- File Upload Logic (SheetJS required) ---
  function updateFileRollList() {
    if (!fileRollList) return;
    fileRollList.innerHTML = fileRolls.length ? fileRolls.map(r => `<span class='badge bg-info me-1 mb-1'>${r}</span>`).join('') : '';
    console.log('File roll list updated:', fileRolls);
  }
  if (fileInput) {
    fileInput.addEventListener('change', function(e) {
      if (fileInput.disabled) return;
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = function(evt) {
        let data = evt.target.result;
        let workbook;
        if (file.name.endsWith('.csv')) {
          workbook = XLSX.read(data, {type: 'binary', codepage: 65001});
        } else {
          workbook = XLSX.read(data, {type: 'binary'});
        }
        let rolls = [];
        workbook.SheetNames.forEach(function(sheetName) {
          const sheet = workbook.Sheets[sheetName];
          const json = XLSX.utils.sheet_to_json(sheet, {header:1});
          json.forEach(row => {
            row.forEach(cell => {
              const val = String(cell).trim();
              if (/^\d{5,}$/.test(val)) rolls.push(val);
            });
          });
        });
        fileRolls = Array.from(new Set(rolls));
        updateFileRollList();
        updateAllocatedRollNumbers();
        console.log('File rolls updated:', fileRolls);
      };
      reader.readAsBinaryString(file);
    });
  }

  // --- Allocated Roll Numbers Display ---
  function updateAllocatedRollNumbers() {
    if (!allocatedDiv) return;
    let allRolls = [];
    if (!isOpenToAll.checked) {
      allRolls = [...specificRolls, ...fileRolls];
      if (startRoll && endRoll) {
        const start = startRoll.value.trim();
        const end = endRoll.value.trim();
        if (/^\d{5,}$/.test(start) && /^\d{5,}$/.test(end) && start <= end) {
          let range = [];
          for (let i = parseInt(start); i <= parseInt(end); i++) range.push(i.toString());
          allRolls = allRolls.concat(range);
        }
      }
      allRolls = Array.from(new Set(allRolls));
    }
    allocatedDiv.innerHTML = allRolls.length ? allRolls.map(r => `<span class='badge bg-success me-1 mb-1'>${r}</span>`).join('') : '<span class="text-muted">No roll numbers allocated yet.</span>';
    console.log('Allocated rolls updated:', allRolls);
  }

  // --- Event Listeners for Live Updates ---
  if (startRoll) startRoll.addEventListener('input', updateAllocatedRollNumbers);
  if (endRoll) endRoll.addEventListener('input', updateAllocatedRollNumbers);
  if (isOpenToAll) isOpenToAll.addEventListener('change', function() {
    setDisabledState();
    updateAllocatedRollNumbers();
  });

  // Initial state
  setDisabledState();
  updateAllocatedRollNumbers();
});
