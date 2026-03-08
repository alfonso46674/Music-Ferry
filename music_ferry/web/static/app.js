// Music Ferry Web UI JavaScript

// Use relative paths to work behind reverse proxy with path prefix
const API_BASE = 'api/v1';

// State
let logsPaused = false;
let eventSource = null;
let currentJobId = null;
let headphonesDevices = [];

// DOM Elements
const elements = {
    syncing: document.getElementById('syncing'),
    lastSync: document.getElementById('last-sync'),
    nextScheduled: document.getElementById('next-scheduled'),
    syncBtn: document.getElementById('sync-btn'),
    scheduleEnabled: document.getElementById('schedule-enabled'),
    scheduleTime: document.getElementById('schedule-time'),
    scheduleSource: document.getElementById('schedule-source'),
    saveScheduleBtn: document.getElementById('save-schedule-btn'),
    scheduleStatus: document.getElementById('schedule-status'),
    spotifyTracks: document.getElementById('spotify-tracks'),
    spotifyPlaylists: document.getElementById('spotify-playlists'),
    spotifySize: document.getElementById('spotify-size'),
    youtubeTracks: document.getElementById('youtube-tracks'),
    youtubePlaylists: document.getElementById('youtube-playlists'),
    youtubeSize: document.getElementById('youtube-size'),
    totalTracks: document.getElementById('total-tracks'),
    totalPlaylists: document.getElementById('total-playlists'),
    totalSize: document.getElementById('total-size'),
    configuredMount: document.getElementById('configured-mount'),
    headphonesCount: document.getElementById('headphones-count'),
    scanHeadphonesBtn: document.getElementById('scan-headphones-btn'),
    headphonesDeviceSelect: document.getElementById('headphones-device-select'),
    ensureAccessBtn: document.getElementById('ensure-access-btn'),
    transferSourceSelect: document.getElementById('transfer-source-select'),
    transferHeadphonesBtn: document.getElementById('transfer-headphones-btn'),
    deleteMp3Btn: document.getElementById('delete-mp3-btn'),
    prepareUnplugBtn: document.getElementById('prepare-unplug-btn'),
    headphonesStatus: document.getElementById('headphones-status'),
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

function setHeadphonesMessage(message, type = '') {
    elements.headphonesStatus.textContent = message;
    elements.headphonesStatus.classList.remove('status-success', 'status-error');
    if (type === 'success') {
        elements.headphonesStatus.classList.add('status-success');
    }
    if (type === 'error') {
        elements.headphonesStatus.classList.add('status-error');
    }
}

function setScheduleMessage(message, type = '') {
    elements.scheduleStatus.textContent = message;
    elements.scheduleStatus.classList.remove('status-success', 'status-error');
    if (type === 'success') {
        elements.scheduleStatus.classList.add('status-success');
    }
    if (type === 'error') {
        elements.scheduleStatus.classList.add('status-error');
    }
}

function getSelectedDevice() {
    const selectedPath = elements.headphonesDeviceSelect.value;
    return headphonesDevices.find((device) => device.mount_path === selectedPath);
}

function updateHeadphonesSelectionMessage() {
    const selected = getSelectedDevice();
    if (!selected) {
        setHeadphonesMessage('No device selected.', 'error');
        return;
    }
    const state = selected.connected ? 'Connected' : 'Not connected';
    const access = selected.accessible ? 'accessible' : 'not accessible';
    setHeadphonesMessage(`${state}, ${access}. ${selected.reason}`);
}

function updateHeadphonesDropdown(configuredMount) {
    const previousSelection = elements.headphonesDeviceSelect.value;
    elements.headphonesDeviceSelect.innerHTML = '';

    if (headphonesDevices.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No candidates found';
        elements.headphonesDeviceSelect.appendChild(option);
        elements.headphonesDeviceSelect.disabled = true;
        return;
    }

    headphonesDevices.forEach((device) => {
        const option = document.createElement('option');
        option.value = device.mount_path;
        const prefix = device.accessible
            ? 'Ready'
            : device.connected
                ? 'Needs setup'
                : 'Offline';
        option.textContent = `${prefix}: ${device.mount_path}`;
        elements.headphonesDeviceSelect.appendChild(option);
    });

    const hasPrevious = headphonesDevices.some((device) => device.mount_path === previousSelection);
    const hasConfigured = headphonesDevices.some((device) => device.mount_path === configuredMount);
    const preferred = headphonesDevices.find((device) => device.connected && device.accessible);

    if (hasPrevious) {
        elements.headphonesDeviceSelect.value = previousSelection;
    } else if (hasConfigured) {
        elements.headphonesDeviceSelect.value = configuredMount;
    } else if (preferred) {
        elements.headphonesDeviceSelect.value = preferred.mount_path;
    } else {
        elements.headphonesDeviceSelect.value = headphonesDevices[0].mount_path;
    }

    elements.headphonesDeviceSelect.disabled = false;
}

function formatScanCandidatesForLog(devices) {
    if (!Array.isArray(devices) || devices.length === 0) {
        return 'none';
    }

    const maxShown = 6;
    const shown = devices.slice(0, maxShown).map((device) => {
        const state = device.accessible
            ? 'ready'
            : device.connected
                ? 'needs-setup'
                : 'offline';
        return `${device.mount_path} (${state})`;
    });

    if (devices.length > maxShown) {
        shown.push(`+${devices.length - maxShown} more`);
    }

    return shown.join(', ');
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
        elements.nextScheduled.textContent = formatDate(data.next_scheduled);
    } catch (error) {
        console.error('Failed to fetch status:', error);
        elements.syncing.textContent = 'Error';
        elements.nextScheduled.textContent = 'Error';
    }
}

async function fetchSchedule() {
    try {
        const response = await fetch(`${API_BASE}/schedule`);
        const data = await response.json();

        if (data.error) {
            setScheduleMessage(data.error, 'error');
            return;
        }

        elements.scheduleEnabled.checked = Boolean(data.enabled);
        elements.scheduleTime.value = data.time || '05:00';
        elements.scheduleSource.value = data.source || 'youtube';

        if (data.enabled) {
            setScheduleMessage(
                `Automatic sync is enabled. Next run: ${formatDate(data.next_run)}.`,
                'success',
            );
        } else {
            setScheduleMessage('Automatic sync is disabled.');
        }
    } catch (error) {
        console.error('Failed to fetch schedule:', error);
        setScheduleMessage('Failed to load schedule settings.', 'error');
    }
}

async function saveSchedule() {
    elements.saveScheduleBtn.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/schedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                enabled: elements.scheduleEnabled.checked,
                time: elements.scheduleTime.value,
                source: elements.scheduleSource.value,
            }),
        });
        const data = await response.json();

        if (data.error) {
            setScheduleMessage(data.error, 'error');
            appendLog(`[ERROR] Schedule update failed: ${data.error}`);
            return;
        }

        setScheduleMessage(
            data.enabled
                ? `Schedule saved. Next run: ${formatDate(data.next_run)}.`
                : 'Schedule disabled.',
            'success',
        );
        appendLog(
            `[INFO] Schedule updated: enabled=${data.enabled} time=${data.time} source=${data.source}`,
        );
        await fetchStatus();
    } catch (error) {
        console.error('Failed to save schedule:', error);
        setScheduleMessage('Failed to save schedule.', 'error');
    } finally {
        elements.saveScheduleBtn.disabled = false;
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

async function scanHeadphones(showStatus = false) {
    try {
        const response = await fetch(`${API_BASE}/headphones/scan`);
        const data = await response.json();

        headphonesDevices = data.devices || [];
        elements.configuredMount.textContent = data.configured_mount || '-';
        elements.headphonesCount.textContent = `${headphonesDevices.length} candidate(s)`;

        updateHeadphonesDropdown(data.configured_mount);
        updateHeadphonesSelectionMessage();

        if (showStatus) {
            const candidateSummary = formatScanCandidatesForLog(headphonesDevices);
            appendLog(
                `[INFO] Headphones scan complete (${headphonesDevices.length} candidates): ${candidateSummary}`,
            );
        }
    } catch (error) {
        console.error('Failed to scan headphones:', error);
        setHeadphonesMessage('Failed to scan headphones.', 'error');
    }
}

async function ensureHeadphonesAccess() {
    const mountPath = elements.headphonesDeviceSelect.value;
    if (!mountPath) {
        setHeadphonesMessage('Select a headphones mount path first.', 'error');
        return;
    }

    elements.ensureAccessBtn.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/headphones/access`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mount_path: mountPath }),
        });
        const data = await response.json();

        if (!data.ok) {
            setHeadphonesMessage(data.message || 'Unable to make device accessible.', 'error');
            appendLog(`[ERROR] Headphones access failed: ${data.message || 'unknown error'}`);
            return;
        }

        setHeadphonesMessage(data.message, 'success');
        appendLog(`[INFO] ${data.message}`);
    } catch (error) {
        console.error('Failed to ensure headphone access:', error);
        setHeadphonesMessage('Failed to check headphones access.', 'error');
    } finally {
        elements.ensureAccessBtn.disabled = false;
    }
}

async function transferToHeadphones() {
    const mountPath = elements.headphonesDeviceSelect.value;
    if (!mountPath) {
        setHeadphonesMessage('Select a headphones mount path first.', 'error');
        return;
    }

    elements.transferHeadphonesBtn.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/headphones/transfer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mount_path: mountPath,
                source: elements.transferSourceSelect.value,
            }),
        });
        const data = await response.json();

        if (!data.ok) {
            setHeadphonesMessage(data.message || 'Transfer failed.', 'error');
            appendLog(`[ERROR] Transfer failed: ${data.message || 'unknown error'}`);
            return;
        }

        setHeadphonesMessage(data.message, 'success');
        appendLog(`[INFO] ${data.message}`);
        fetchLibrary();
    } catch (error) {
        console.error('Failed to transfer to headphones:', error);
        setHeadphonesMessage('Transfer request failed.', 'error');
    } finally {
        elements.transferHeadphonesBtn.disabled = false;
    }
}

async function deleteHeadphonesMp3() {
    const mountPath = elements.headphonesDeviceSelect.value;
    if (!mountPath) {
        setHeadphonesMessage('Select a headphones mount path first.', 'error');
        return;
    }

    if (!window.confirm(`Delete all .mp3 files under ${mountPath}?`)) {
        return;
    }

    elements.deleteMp3Btn.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/headphones/delete-mp3`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mount_path: mountPath }),
        });
        const data = await response.json();

        if (!data.ok) {
            setHeadphonesMessage(data.message || 'Delete failed.', 'error');
            appendLog(`[ERROR] Delete failed: ${data.message || 'unknown error'}`);
            return;
        }

        setHeadphonesMessage(data.message, 'success');
        appendLog(`[INFO] ${data.message}`);
    } catch (error) {
        console.error('Failed to delete MP3 files on headphones:', error);
        setHeadphonesMessage('Delete request failed.', 'error');
    } finally {
        elements.deleteMp3Btn.disabled = false;
    }
}

async function prepareHeadphonesUnplug() {
    const mountPath = elements.headphonesDeviceSelect.value;
    if (!mountPath) {
        setHeadphonesMessage('Select a headphones mount path first.', 'error');
        return;
    }

    elements.prepareUnplugBtn.disabled = true;
    setHeadphonesMessage(`Preparing safe unplug for ${mountPath}...`);
    appendLog(`[INFO] Prepare safe unplug requested for ${mountPath}`);
    try {
        const response = await fetch(`${API_BASE}/headphones/prepare-unplug`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mount_path: mountPath }),
        });
        const data = await response.json();

        if (!data.ok) {
            setHeadphonesMessage(data.message || 'Prepare-unplug failed.', 'error');
            appendLog(`[ERROR] Prepare-unplug failed: ${data.message || 'unknown error'}`);
            return;
        }

        setHeadphonesMessage(data.message, 'success');
        appendLog(`[INFO] ${data.message}`);
    } catch (error) {
        console.error('Failed to prepare headphones unplug:', error);
        setHeadphonesMessage('Prepare-unplug request failed.', 'error');
    } finally {
        elements.prepareUnplugBtn.disabled = false;
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
elements.scanHeadphonesBtn.addEventListener('click', () => scanHeadphones(true));
elements.ensureAccessBtn.addEventListener('click', ensureHeadphonesAccess);
elements.transferHeadphonesBtn.addEventListener('click', transferToHeadphones);
elements.deleteMp3Btn.addEventListener('click', deleteHeadphonesMp3);
elements.prepareUnplugBtn.addEventListener('click', prepareHeadphonesUnplug);
elements.headphonesDeviceSelect.addEventListener('change', updateHeadphonesSelectionMessage);
elements.saveScheduleBtn.addEventListener('click', saveSchedule);
elements.toggleLogs.addEventListener('click', toggleLogs);
elements.clearLogs.addEventListener('click', clearLogs);

// Initialization
async function init() {
    // Fetch initial data
    await Promise.all([
        fetchStatus(),
        fetchSchedule(),
        fetchLibrary(),
    ]);

    // Connect log stream
    connectLogStream();

    // Refresh status periodically
    setInterval(fetchStatus, 10000);
    setInterval(fetchSchedule, 30000);
    setInterval(fetchLibrary, 30000);
    // Keep scans manual (button/actions) to avoid unintended autofs mount churn.

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
