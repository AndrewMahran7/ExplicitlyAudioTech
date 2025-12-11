// Global variables
let currentJobId = null;
let startTime = null;
let pollInterval = null;

// DOM Elements
const uploadSection = document.getElementById('uploadSection');
const processingSection = document.getElementById('processingSection');
const resultsSection = document.getElementById('resultsSection');
const errorSection = document.getElementById('errorSection');

const uploadForm = document.getElementById('uploadForm');
const fileInput = document.getElementById('fileInput');
const fileName = document.getElementById('fileName');
const submitBtn = document.getElementById('submitBtn');

const processingFilename = document.getElementById('processingFilename');
const statusText = document.getElementById('statusText');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const processingModel = document.getElementById('processingModel');
const processingMethod = document.getElementById('processingMethod');
const processingDevice = document.getElementById('processingDevice');

const profaneCount = document.getElementById('profaneCount');
const processingTime = document.getElementById('processingTime');
const downloadAudio = document.getElementById('downloadAudio');
const downloadReport = document.getElementById('downloadReport');

const errorMessage = document.getElementById('errorMessage');
const processAnotherBtn = document.getElementById('processAnotherBtn');
const tryAgainBtn = document.getElementById('tryAgainBtn');

// Lyrics Fetcher Elements
const searchInput = document.getElementById('searchInput');
const searchResults = document.getElementById('searchResults');
const lyricsInput = document.getElementById('lyricsInput');
const lyricsStatus = document.getElementById('lyricsStatus');

// Search suggestion state
let searchTimeout = null;
let selectedSong = null;

// Event Listeners
fileInput.addEventListener('change', handleFileSelect);
uploadForm.addEventListener('submit', handleSubmit);
processAnotherBtn.addEventListener('click', resetForm);
tryAgainBtn.addEventListener('click', resetForm);
searchInput.addEventListener('input', handleSearchInput);

// Input type toggle
const inputTypeRadios = document.querySelectorAll('input[name="input_type"]');
const fileUploadGroup = document.getElementById('fileUploadGroup');
const youtubeUrlGroup = document.getElementById('youtubeUrlGroup');
const youtubeUrlInput = document.getElementById('youtubeUrl');

inputTypeRadios.forEach(radio => {
    radio.addEventListener('change', handleInputTypeChange);
});

function handleInputTypeChange(e) {
    const inputType = e.target.value;
    
    if (inputType === 'file') {
        fileUploadGroup.style.display = 'block';
        youtubeUrlGroup.style.display = 'none';
        fileInput.required = true;
        youtubeUrlInput.required = false;
    } else {
        fileUploadGroup.style.display = 'none';
        youtubeUrlGroup.style.display = 'block';
        fileInput.required = false;
        youtubeUrlInput.required = true;
    }
}

// Handle file selection
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        fileName.textContent = file.name;
    }
}

// Handle form submission
async function handleSubmit(e) {
    e.preventDefault();

    const inputType = document.querySelector('input[name="input_type"]:checked').value;
    const formData = new FormData();

    // Validate based on input type
    if (inputType === 'file') {
        const file = fileInput.files[0];
        if (!file) {
            showError('Please select a file');
            return;
        }

        // Validate file size (100MB)
        if (file.size > 100 * 1024 * 1024) {
            showError('File size exceeds 100MB limit');
            return;
        }

        formData.append('file', file);
    } else {
        const youtubeUrl = youtubeUrlInput.value.trim();
        if (!youtubeUrl) {
            showError('Please enter a YouTube URL');
            return;
        }

        // Basic YouTube URL validation
        if (!youtubeUrl.includes('youtube.com') && !youtubeUrl.includes('youtu.be')) {
            showError('Please enter a valid YouTube URL');
            return;
        }

        formData.append('youtube_url', youtubeUrl);
    }

    // Add other form data
    formData.append('input_type', inputType);
    formData.append('model', document.querySelector('input[name="model"]:checked').value);
    formData.append('method', document.querySelector('input[name="method"]:checked').value);
    formData.append('device', document.querySelector('input[name="device"]:checked').value);
    
    // Add optional lyrics
    const lyrics = document.getElementById('lyricsInput').value.trim();
    if (lyrics) {
        formData.append('lyrics', lyrics);
    }

    // Disable submit button
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="btn-text">⏳ ' + (inputType === 'youtube' ? 'Downloading...' : 'Uploading...') + '</span>';

    try {
        // Upload file
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Upload failed');
        }

        const data = await response.json();
        currentJobId = data.job_id;
        startTime = Date.now();

        // Show processing section
        const displayName = inputType === 'file' ? fileInput.files[0].name : 'YouTube Video';
        showProcessing(displayName);

        // Start polling for status
        pollStatus();

    } catch (error) {
        showError(error.message);
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span class="btn-text">🚀 Start Processing</span>';
    }
}

// Show processing section
function showProcessing(filename) {
    uploadSection.style.display = 'none';
    processingSection.style.display = 'block';
    resultsSection.style.display = 'none';
    errorSection.style.display = 'none';

    processingFilename.textContent = filename;
    
    const model = document.querySelector('input[name="model"]:checked').value;
    const method = document.querySelector('input[name="method"]:checked').value;
    const device = document.querySelector('input[name="device"]:checked').value;

    processingModel.textContent = model.charAt(0).toUpperCase() + model.slice(1);
    processingMethod.textContent = method.charAt(0).toUpperCase() + method.slice(1);
    processingDevice.textContent = device.toUpperCase();
}

// Poll for job status
function pollStatus() {
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/status/${currentJobId}`);
            
            if (!response.ok) {
                throw new Error('Failed to get status');
            }

            const status = await response.json();
            updateProgress(status);

            if (status.status === 'completed') {
                clearInterval(pollInterval);
                showResults(status);
            } else if (status.status === 'failed') {
                clearInterval(pollInterval);
                showError(status.error || 'Processing failed');
            }

        } catch (error) {
            console.error('Status poll error:', error);
            clearInterval(pollInterval);
            showError('Connection error. Please refresh the page.');
        }
    }, 1000); // Poll every second
}

// Update progress display
function updateProgress(status) {
    const progress = status.progress || 0;
    progressFill.style.width = `${progress}%`;
    progressText.textContent = `${Math.round(progress)}%`;
    statusText.textContent = status.step || 'Processing...';
}

// Show results section
function showResults(status) {
    uploadSection.style.display = 'none';
    processingSection.style.display = 'none';
    resultsSection.style.display = 'block';
    errorSection.style.display = 'none';

    // Calculate processing time
    const timeElapsed = Math.round((Date.now() - startTime) / 1000);
    const minutes = Math.floor(timeElapsed / 60);
    const seconds = timeElapsed % 60;
    const timeStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;

    profaneCount.textContent = status.profane_count || 0;
    processingTime.textContent = timeStr;

    // Set download links
    downloadAudio.href = `/download/${currentJobId}`;
    downloadReport.href = `/report/${currentJobId}`;
}

// Show error section
function showError(message) {
    uploadSection.style.display = 'none';
    processingSection.style.display = 'none';
    resultsSection.style.display = 'none';
    errorSection.style.display = 'block';

    errorMessage.textContent = message;
}

// Reset form
function resetForm() {
    uploadSection.style.display = 'block';
    processingSection.style.display = 'none';
    resultsSection.style.display = 'none';
    errorSection.style.display = 'none';

    uploadForm.reset();
    fileName.textContent = 'Choose an audio file...';
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span class="btn-text">🚀 Start Processing</span>';

    progressFill.style.width = '0%';
    progressText.textContent = '0%';

    currentJobId = null;
    startTime = null;

    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// Handle search input with debouncing
function handleSearchInput(e) {
    const term = e.target.value.trim();
    
    // Clear previous timeout
    if (searchTimeout) {
        clearTimeout(searchTimeout);
    }
    
    // Clear results if empty
    if (!term) {
        clearSearchResults();
        return;
    }
    
    // Debounce search by 300ms
    searchTimeout = setTimeout(() => {
        searchSuggestions(term);
    }, 300);
}

// Clear search results
function clearSearchResults() {
    searchResults.innerHTML = '';
    searchResults.style.display = 'none';
}

// Search for song suggestions
async function searchSuggestions(term) {
    try {
        const response = await fetch(`https://api.lyrics.ovh/suggest/${encodeURIComponent(term)}`);
        
        if (!response.ok) {
            throw new Error('Search failed');
        }
        
        const data = await response.json();
        displaySearchResults(data.data);
        
    } catch (error) {
        console.error('Search error:', error);
        clearSearchResults();
    }
}

// Display search results
function displaySearchResults(results) {
    // Clear previous results
    clearSearchResults();
    
    if (!results || results.length === 0) {
        return;
    }
    
    // Track unique results (avoid duplicates)
    const seenResults = new Set();
    const uniqueResults = [];
    
    for (const result of results) {
        if (uniqueResults.length >= 5) break;
        
        const key = `${result.title} - ${result.artist.name}`;
        if (seenResults.has(key)) continue;
        
        seenResults.add(key);
        uniqueResults.push({
            display: key,
            artist: result.artist.name,
            title: result.title
        });
    }
    
    // Create result elements
    uniqueResults.forEach((result, index) => {
        const resultItem = document.createElement('div');
        resultItem.className = 'search-result-item';
        if (index === uniqueResults.length - 1) {
            resultItem.classList.add('search-result-last');
        }
        resultItem.textContent = result.display;
        
        // Click handler to fetch lyrics
        resultItem.addEventListener('click', () => {
            fetchLyrics(result);
        });
        
        searchResults.appendChild(resultItem);
    });
    
    searchResults.style.display = 'block';
}

// Fetch lyrics for selected song
async function fetchLyrics(song) {
    console.log('Fetching lyrics for:', song);
    
    // Clear search results and input
    clearSearchResults();
    searchInput.value = song.display;
    selectedSong = song;
    
    // Show loading state
    lyricsStatus.textContent = '⏳ Fetching lyrics...';
    lyricsStatus.className = 'lyrics-status loading';
    
    try {
        const encodedArtist = encodeURIComponent(song.artist);
        const encodedTitle = encodeURIComponent(song.title);
        
        const response = await fetch(`https://api.lyrics.ovh/v1/${encodedArtist}/${encodedTitle}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Lyrics not found for this song.');
            }
            throw new Error('Failed to fetch lyrics. Please try again.');
        }
        
        const data = await response.json();
        
        if (!data.lyrics) {
            throw new Error('No lyrics found in response.');
        }
        
        // Autofill the textarea with fetched lyrics
        lyricsInput.value = data.lyrics.trim();
        
        // Show success message
        lyricsStatus.textContent = `✅ Lyrics loaded for "${song.title}" by ${song.artist}`;
        lyricsStatus.className = 'lyrics-status success';
        
        // Scroll lyrics textarea into view
        lyricsInput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
    } catch (error) {
        console.error('Lyrics fetch error:', error);
        lyricsStatus.textContent = `❌ ${error.message}`;
        lyricsStatus.className = 'lyrics-status error';
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (pollInterval) {
        clearInterval(pollInterval);
    }
});
