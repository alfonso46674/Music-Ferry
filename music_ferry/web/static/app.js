// Music Ferry Web UI JavaScript

// Use relative paths to work behind reverse proxy with path prefix
const API_BASE = 'api/v1';

// State
let logsPaused = false;
let eventSource = null;
let currentJobId = null;

// DOM Elements
const elements = {
    syncing: document.getElementById('syncing'),
    lastSync: document.getElementById('last-sync'),
    syncBtn: document.getElementById('sync-btn'),
    spotifyTracks: document.getElementById('spotify-tracks'),
    spotifyPlaylists: document.getElementById('spotify-playlists'),
    spotifySize: document.getElementById('spotify-size'),
    youtubeTracks: document.getElementById('youtube-tracks'),
    youtubePlaylists: document.getElementById('youtube-playlists'),
    youtubeSize: document.getElementById('youtube-size'),
    totalTracks: document.getElementById('total-tracks'),
    totalPlaylists: document.getElementById('total-playlists'),
    totalSize: document.getElementById('total-size'),
    logs: document.getElementById('logs'),
    toggleLogs: document.getElementById('toggle-logs'),
    clearLogs: document.getElementById('clear-logs'),
    version: document.getElementById('version'),
};

// Utilities
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(isoString) {
    if (!isoString) return 'Never';
    const date = new Date(isoString);
    return date.toLocaleString();
}

// API Functions
async function fetchStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();

        elements.syncing.textContent = data.syncing ? 'Yes' : 'No';
        if (data.syncing) {
            elements.syncing.classList.add('syncing-active');
            elements.syncBtn.disabled = true;
            currentJobId = data.current_job_id;
        } else {
            elements.syncing.classList.remove('syncing-active');
            elements.syncBtn.disabled = false;
            currentJobId = null;
        }

        elements.lastSync.textContent = formatDate(data.last_sync);
    } catch (error) {
        console.error('Failed to fetch status:', error);
        elements.syncing.textContent = 'Error';
    }
}

async function fetchLibrary() {
    try {
        const response = await fetch(`${API_BASE}/library`);
        const data = await response.json();

        // Spotify
        elements.spotifyTracks.textContent = data.spotify.tracks;
        elements.spotifyPlaylists.textContent = data.spotify.playlists;
        elements.spotifySize.textContent = formatBytes(data.spotify.size_bytes);

        // YouTube
        elements.youtubeTracks.textContent = data.youtube.tracks;
        elements.youtubePlaylists.textContent = data.youtube.playlists;
        elements.youtubeSize.textContent = formatBytes(data.youtube.size_bytes);

        // Total
        elements.totalTracks.textContent = data.total.tracks;
        elements.totalPlaylists.textContent = data.total.playlists;
        elements.totalSize.textContent = formatBytes(data.total.size_bytes);
    } catch (error) {
        console.error('Failed to fetch library:', error);
    }
}

async function triggerSync() {
    try {
        elements.syncBtn.disabled = true;
        const response = await fetch(`${API_BASE}/sync`, { method: 'POST' });
        const data = await response.json();

        if (data.error) {
            alert('Sync already in progress');
            return;
        }

        currentJobId = data.job_id;
        appendLog(`[INFO] Sync started (job: ${data.job_id})`);

        // Poll for updates
        pollSyncStatus(data.job_id);
    } catch (error) {
        console.error('Failed to trigger sync:', error);
        alert('Failed to start sync');
        elements.syncBtn.disabled = false;
    }
}

async function pollSyncStatus(jobId) {
    const poll = async () => {
        try {
            const response = await fetch(`${API_BASE}/sync/${jobId}`);
            const data = await response.json();

            if (data.status === 'completed') {
                appendLog(`[INFO] Sync completed: ${data.result?.total_tracks || 0} tracks`);
                elements.syncBtn.disabled = false;
                fetchStatus();
                fetchLibrary();
                return;
            }

            if (data.status === 'failed') {
                appendLog(`[ERROR] Sync failed: ${data.error}`);
                elements.syncBtn.disabled = false;
                fetchStatus();
                return;
            }

            // Still running, poll again
            setTimeout(poll, 2000);
        } catch (error) {
            console.error('Failed to poll sync status:', error);
            setTimeout(poll, 5000);
        }
    };

    poll();
}

// Log Streaming
function connectLogStream() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource(`${API_BASE}/logs/stream`);

    eventSource.addEventListener('log', (event) => {
        if (!logsPaused) {
            appendLog(event.data);
        }
    });

    eventSource.onerror = () => {
        console.error('Log stream error, reconnecting...');
        setTimeout(connectLogStream, 3000);
    };
}

function appendLog(line) {
    const maxLines = 500;
    const lines = elements.logs.textContent.split('\n');

    lines.push(line);

    if (lines.length > maxLines) {
        lines.splice(0, lines.length - maxLines);
    }

    elements.logs.textContent = lines.join('\n');

    // Auto-scroll to bottom
    const container = document.getElementById('logs-container');
    container.scrollTop = container.scrollHeight;
}

function toggleLogs() {
    logsPaused = !logsPaused;
    elements.toggleLogs.textContent = logsPaused ? 'Resume' : 'Pause';
}

function clearLogs() {
    elements.logs.textContent = '';
}

// Event Listeners
elements.syncBtn.addEventListener('click', triggerSync);
elements.toggleLogs.addEventListener('click', toggleLogs);
elements.clearLogs.addEventListener('click', clearLogs);

// Initialization
async function init() {
    // Fetch initial data
    await Promise.all([
        fetchStatus(),
        fetchLibrary(),
    ]);

    // Connect log stream
    connectLogStream();

    // Refresh status periodically
    setInterval(fetchStatus, 10000);
    setInterval(fetchLibrary, 30000);

    // Set version (from OpenAPI spec)
    try {
        const response = await fetch('openapi.json');
        const data = await response.json();
        elements.version.textContent = data.info?.version || '-';
    } catch {
        elements.version.textContent = '-';
    }
}

// Start the app
init();
