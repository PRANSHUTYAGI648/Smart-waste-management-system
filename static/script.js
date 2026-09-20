// Global Application State
let dustbinData = [];
let depotData = { latitude: 28.6135, longitude: 77.2085, name: "Central Municipal Waste Depot" };
let currentFilter = { status: "all", type: "all", search: "" };
let autoStreamInterval = null;
let soundAlertsEnabled = true;

// Map & Chart Instances
let leafletMap = null;
let mapMarkers = [];
let routePolyline = null;
let telemetryChartInstance = null;
let binTypeChartInstance = null;

// Tab Switcher
function switchTab(tabId) {
    document.querySelectorAll(".nav-tab").forEach(tab => tab.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));

    const activeTabBtn = document.querySelector(`.nav-tab[onclick*='${tabId}']`);
    if (activeTabBtn) activeTabBtn.classList.add("active");

    const targetContent = document.getElementById(`tab-${tabId}`);
    if (targetContent) targetContent.classList.add("active");

    // Re-render GIS Map when tab becomes visible
    if (tabId === "gis-map" && leafletMap) {
        setTimeout(() => {
            leafletMap.invalidateSize();
        }, 200);
    }
}

// Web Audio API Sound Chime Synthesizer
function playOverflowAlertSound() {
    if (!soundAlertsEnabled) return;
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        
        // High alert tone sequence (880Hz -> 1046Hz)
        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.type = "sine";
        osc1.frequency.setValueAtTime(880, ctx.currentTime);
        osc1.frequency.exponentialRampToValueAtTime(1046.5, ctx.currentTime + 0.15);
        gain1.gain.setValueAtTime(0.3, ctx.currentTime);
        gain1.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
        
        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start();
        osc1.stop(ctx.currentTime + 0.3);
    } catch (e) {
        console.warn("Audio Context error:", e);
    }
}

function toggleSoundAlerts() {
    soundAlertsEnabled = !soundAlertsEnabled;
    const soundStatus = document.getElementById("soundStatus");
    if (soundStatus) soundStatus.innerText = soundAlertsEnabled ? "On" : "Off";
}

// Fetch Main Telemetry Data
async function loadDustbinData() {
    try {
        const response = await fetch("/api/dustbins");
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        dustbinData = data.dustbins || [];
        if (data.depot) depotData = data.depot;

        renderOverviewMetrics();
        renderAlertsAndBars();
        renderDustbinGrid();
        updateGISMap();
        loadRouteOptimization();
        loadAnalyticsData();

        const lastUpdatedTime = document.getElementById("lastUpdatedTime");
        if (lastUpdatedTime) {
            lastUpdatedTime.innerText = `Updated: ${new Date().toLocaleTimeString()}`;
        }
    } catch (error) {
        console.error("Error loading dustbin telemetry data:", error);
    }
}

// Overview Summary Metrics
function renderOverviewMetrics() {
    let normalCount = 0;
    let warningCount = 0;
    let fullCount = 0;
    let totalFill = 0;

    dustbinData.forEach(bin => {
        totalFill += bin.waste_level;
        if (bin.status === "Normal") normalCount++;
        else if (bin.status === "Warning") warningCount++;
        else if (bin.status === "Full") fullCount++;
    });

    const totalEl = document.getElementById("totalDustbins");
    const normalEl = document.getElementById("normalCount");
    const warningEl = document.getElementById("warningCount");
    const fullEl = document.getElementById("fullCount");

    if (totalEl) totalEl.textContent = dustbinData.length;
    if (normalEl) normalEl.textContent = normalCount;
    if (warningEl) warningEl.textContent = warningCount;
    if (fullEl) fullEl.textContent = fullCount;

    if (fullCount > 0) {
        playOverflowAlertSound();
    }
}

// Alerts & Real-Time Fill Bars
function renderAlertsAndBars() {
    const alertsContainer = document.getElementById("alertsContainer");
    const chartRowsContainer = document.getElementById("chartRowsContainer");

    if (alertsContainer) {
        let alertHtml = "";
        dustbinData.forEach(bin => {
            if (bin.status === "Full") {
                alertHtml += `
                    <div class="alert full-alert">
                        <span class="alert-icon">🚨</span>
                        <div class="alert-content">
                            <strong>Immediate Pickup Required!</strong> Dustbin #${bin.id} - ${bin.location} is at ${bin.waste_level}% capacity (${bin.bin_type || 'General'}).
                        </div>
                        <button class="alert-action-btn" onclick="collectDustbin(${bin.id})">Mark Collected</button>
                    </div>
                `;
            } else if (bin.status === "Warning") {
                alertHtml += `
                    <div class="alert warning-alert">
                        <span class="alert-icon">⚠️</span>
                        <div class="alert-content">
                            <strong>Approaching Capacity:</strong> Dustbin #${bin.id} - ${bin.location} is at ${bin.waste_level}% fill level.
                        </div>
                    </div>
                `;
            }
        });
        alertsContainer.innerHTML = alertHtml || `<div class="alert warning-alert" style="background: rgba(0, 255, 157, 0.1); border-color: rgba(0, 255, 157, 0.3); color: #00ff9d;">✅ All bin nodes are currently operating within safe capacity limits.</div>`;
    }

    if (chartRowsContainer) {
        chartRowsContainer.innerHTML = dustbinData.map(bin => {
            let fillClass = "bar-fill-normal";
            if (bin.status === "Warning") fillClass = "bar-fill-warning";
            if (bin.status === "Full") fillClass = "bar-fill-full";

            return `
                <div class="chart-row">
                    <div class="chart-label">
                        <span class="bin-title">
                            <strong>#${bin.id}</strong> ${bin.location}
                            <span class="bin-type-badge">${bin.bin_type || 'General Waste'}</span>
                        </span>
                        <span class="percentage" id="percentage${bin.id}">${bin.waste_level}%</span>
                    </div>
                    <div class="bar-background">
                        <div class="bar-fill ${fillClass}" id="bar${bin.id}" style="width: ${bin.waste_level}%"></div>
                    </div>
                </div>
            `;
        }).join("");
    }
}

// Bin Nodes Directory Cards
function renderDustbinGrid() {
    const container = document.getElementById("dustbinContainer");
    if (!container) return;

    const filtered = dustbinData.filter(bin => {
        const matchesSearch = currentFilter.search === "" ||
            bin.location.toLowerCase().includes(currentFilter.search.toLowerCase()) ||
            bin.id.toString() === currentFilter.search;

        const matchesStatus = currentFilter.status === "all" || bin.status === currentFilter.status;
        const matchesType = currentFilter.type === "all" || bin.bin_type === currentFilter.type;

        return matchesSearch && matchesStatus && matchesType;
    });

    if (filtered.length === 0) {
        container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px;">No dustbin nodes found matching criteria.</div>`;
        return;
    }

    container.innerHTML = filtered.map(bin => {
        let statusBadge = "🟢 Normal";
        if (bin.status === "Warning") statusBadge = "🟡 Warning";
        if (bin.status === "Full") statusBadge = "🔴 Full Critical";

        const isPending = bin.collection_status === "Pending";
        const collectBtn = isPending
            ? `<button class="btn btn-primary-sm" onclick="collectDustbin(${bin.id})">🚮 Mark Cleaned</button>`
            : `<span style="color: #00ff9d; font-weight: 700; font-size: 0.875rem;">✅ Cleaned</span>`;

        return `
            <div class="dustbin-card">
                <div>
                    <div class="card-top">
                        <div>
                            <span class="bin-id-badge">ID #${bin.id}</span>
                            <h3>${bin.location}</h3>
                        </div>
                        <span class="bin-type-badge">${bin.bin_type || 'General Waste'}</span>
                    </div>

                    <div class="card-row">
                        <span>Fill Capacity:</span>
                        <strong id="wasteLevel${bin.id}">${bin.waste_level}% (${bin.capacity_liters || 120}L)</strong>
                    </div>
                    <div class="card-row">
                        <span>Current Status:</span>
                        <strong id="status${bin.id}">${statusBadge}</strong>
                    </div>
                    <div class="card-row">
                        <span>IoT Battery Health:</span>
                        <strong>🔋 ${bin.battery_level || 90}%</strong>
                    </div>
                    <div class="card-row">
                        <span>Collection Status:</span>
                        <strong id="collection${bin.id}">${bin.collection_status}</strong>
                    </div>
                </div>

                <div class="card-actions">
                    ${collectBtn}
                    <button class="btn btn-danger-sm" onclick="deleteDustbin(${bin.id})" title="Decommission Node">🗑️</button>
                </div>
            </div>
        `;
    }).join("");
}

// Leaflet GIS Map Initialization & Updating
function initGISMap() {
    const mapElement = document.getElementById("map");
    if (!mapElement || leafletMap) return;

    leafletMap = L.map('map').setView([depotData.latitude, depotData.longitude], 14);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
    }).addTo(leafletMap);
}

function updateGISMap() {
    if (!leafletMap) initGISMap();
    if (!leafletMap) return;

    // Clear existing markers
    mapMarkers.forEach(m => leafletMap.removeLayer(m));
    mapMarkers = [];

    // Depot Marker (Neon Cyan)
    const depotIcon = L.divIcon({
        className: 'custom-depot-marker',
        html: `<div style="background: #00e5ff; width: 18px; height: 18px; border-radius: 50%; border: 3px solid #030712; box-shadow: 0 0 16px #00e5ff;"></div>`,
        iconSize: [22, 22]
    });

    const depotMarker = L.marker([depotData.latitude, depotData.longitude], { icon: depotIcon })
        .addTo(leafletMap)
        .bindPopup(`<strong>🏭 ${depotData.name}</strong><br>Central Fleet Dispatch Hub`);
    mapMarkers.push(depotMarker);

    // Bin Markers (Neon Green, Yellow, Crimson)
    dustbinData.forEach(bin => {
        let color = "#00ff9d";
        if (bin.status === "Warning") color = "#ffbe0b";
        if (bin.status === "Full") color = "#ff0055";

        const icon = L.divIcon({
            className: 'custom-bin-marker',
            html: `<div style="background: ${color}; width: 22px; height: 22px; border-radius: 50%; border: 3px solid #030712; box-shadow: 0 0 14px ${color}; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 800; color: #000;">${bin.id}</div>`,
            iconSize: [26, 26]
        });

        const marker = L.marker([bin.latitude, bin.longitude], { icon: icon })
            .addTo(leafletMap)
            .bindPopup(`
                <div style="font-family: sans-serif;">
                    <strong style="font-size: 1.05rem;">Dustbin #${bin.id} - ${bin.location}</strong><br>
                    <span style="color: ${color}; font-weight: bold;">Fill Level: ${bin.waste_level}% (${bin.status})</span><br>
                    <small>Category: ${bin.bin_type || 'General'}</small><br>
                    <small>Battery: 🔋 ${bin.battery_level}% | Signal: ${bin.signal_rssi || -65}dBm</small><br>
                    <button style="margin-top: 8px; background: #00ff9d; color: #030712; border: none; padding: 6px 12px; border-radius: 6px; font-weight: bold; cursor: pointer;" onclick="collectDustbin(${bin.id})">Mark Collected</button>
                </div>
            `);
        mapMarkers.push(marker);
    });
}

// Vehicle Route Optimization Engine
async function loadRouteOptimization() {
    try {
        const response = await fetch("/api/route-optimization");
        const data = await response.json();

        if (!data.success) return;

        const routeStopsCount = document.getElementById("routeStopsCount");
        const routeTotalDist = document.getElementById("routeTotalDist");
        const routeEstTime = document.getElementById("routeEstTime");
        const routeFuelSaved = document.getElementById("routeFuelSaved");
        const routeDistance = document.getElementById("routeDistance");
        const timelineContainer = document.getElementById("dispatchTimeline");

        if (routeStopsCount) routeStopsCount.textContent = data.bins_to_collect;
        if (routeTotalDist) routeTotalDist.textContent = `${data.total_distance_km} km`;
        if (routeEstTime) routeEstTime.textContent = `${data.estimated_time_mins} mins`;
        if (routeFuelSaved) routeFuelSaved.textContent = `${data.fuel_saved_liters} L`;
        if (routeDistance) routeDistance.textContent = `${data.total_distance_km} km`;

        // Render route line on map
        if (leafletMap && data.route && data.route.length > 0) {
            if (routePolyline) leafletMap.removeLayer(routePolyline);

            const latlngs = [
                [depotData.latitude, depotData.longitude],
                ...data.route.map(b => [b.latitude, b.longitude]),
                [depotData.latitude, depotData.longitude]
            ];

            routePolyline = L.polyline(latlngs, {
                color: '#00e5ff',
                weight: 4,
                dashArray: '8, 8',
                lineCap: 'round'
            }).addTo(leafletMap);
        }

        // Render timeline sidebar
        if (timelineContainer) {
            if (data.route.length === 0) {
                timelineContainer.innerHTML = `<div class="timeline-empty" style="color: #00ff9d; font-weight: 600;">✅ All bins operating within safe capacity limits. No pickup dispatch needed!</div>`;
            } else {
                let html = `
                    <div class="timeline-item depot-stop">
                        <div class="timeline-badge">🏁</div>
                        <div class="timeline-info">
                            <h4>Depot Departure</h4>
                            <p>${depotData.name}</p>
                        </div>
                    </div>
                `;

                data.route.forEach(bin => {
                    const stopClass = bin.status === "Full" ? "full-stop" : "warning-stop";
                    html += `
                        <div class="timeline-item ${stopClass}">
                            <div class="timeline-badge">${bin.stop_number}</div>
                            <div class="timeline-info">
                                <h4>Stop #${bin.stop_number}: Dustbin #${bin.id} - ${bin.location}</h4>
                                <p>Fill: ${bin.waste_level}% | Category: ${bin.bin_type} | +${bin.distance_from_prev_km} km</p>
                            </div>
                        </div>
                    `;
                });

                html += `
                    <div class="timeline-item depot-stop">
                        <div class="timeline-badge">🏁</div>
                        <div class="timeline-info">
                            <h4>Return to Depot</h4>
                            <p>Trip Completed • ${data.total_distance_km} km Total</p>
                        </div>
                    </div>
                `;
                timelineContainer.innerHTML = html;
            }
        }
    } catch (e) {
        console.error("Route Optimization Error:", e);
    }
}

// Chart.js Time-Series & Analytics Graphs
async function loadAnalyticsData() {
    try {
        const response = await fetch("/api/analytics");
        const data = await response.json();
        if (!data.success) return;

        // Telemetry Trend Line Chart
        const trendCanvas = document.getElementById("telemetryTrendChart");
        if (trendCanvas) {
            const labels = (data.recent_telemetry_logs || []).map((l, idx) => `T-${idx + 1}`);
            const dataset = (data.recent_telemetry_logs || []).map(l => l.waste_level);

            if (telemetryChartInstance) telemetryChartInstance.destroy();

            telemetryChartInstance = new Chart(trendCanvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Waste Level Fill %',
                        data: dataset,
                        borderColor: '#00ff9d',
                        backgroundColor: 'rgba(0, 255, 157, 0.12)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { min: 0, max: 100, grid: { color: 'rgba(255, 255, 255, 0.06)' } },
                        x: { grid: { color: 'rgba(255, 255, 255, 0.06)' } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        // Bin Type Distribution Doughnut Chart
        const distCanvas = document.getElementById("binTypeDistributionChart");
        if (distCanvas) {
            const types = Object.keys(data.bin_type_distribution || {});
            const counts = Object.values(data.bin_type_distribution || {});

            if (binTypeChartInstance) binTypeChartInstance.destroy();

            binTypeChartInstance = new Chart(distCanvas, {
                type: 'doughnut',
                data: {
                    labels: types,
                    datasets: [{
                        data: counts,
                        backgroundColor: ['#00ff9d', '#00e5ff', '#ffbe0b', '#a855f7', '#ff0055'],
                        borderWidth: 2,
                        borderColor: '#030712'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#f8fafc', font: { size: 11, family: 'Plus Jakarta Sans' } } }
                    }
                }
            });
        }
    } catch (e) {
        console.error("Analytics Load Error:", e);
    }
}

// User Actions
async function collectDustbin(dustbinId) {
    try {
        const response = await fetch(`/collect/${dustbinId}`, { method: "POST" });
        const data = await response.json();
        if (data.success) {
            await loadDustbinData();
        }
    } catch (error) {
        console.error("Collection Error:", error);
    }
}

async function deleteDustbin(dustbinId) {
    if (!confirm(`Are you sure you want to decommission Dustbin #${dustbinId}?`)) return;
    try {
        const response = await fetch(`/api/dustbin/${dustbinId}`, { method: "DELETE" });
        const data = await response.json();
        if (data.success) {
            await loadDustbinData();
        }
    } catch (error) {
        console.error("Delete Error:", error);
    }
}

async function triggerSimulation() {
    try {
        const simBtn = document.getElementById("simBtn");
        if (simBtn) {
            simBtn.disabled = true;
            simBtn.innerText = "⏳ Simulating...";
        }

        await fetch("/api/simulate", { method: "POST" });
        await loadDustbinData();

        if (simBtn) {
            simBtn.disabled = false;
            simBtn.innerText = "⚡ Pulse Telemetry";
        }
    } catch (error) {
        console.error("Simulation Error:", error);
    }
}

function toggleAutoStream() {
    const btn = document.getElementById("autoStreamBtn");
    if (autoStreamInterval) {
        clearInterval(autoStreamInterval);
        autoStreamInterval = null;
        if (btn) {
            btn.innerText = "▶ Stream";
            btn.classList.remove("btn-primary-sm");
            btn.classList.add("btn-outline-sm");
        }
    } else {
        autoStreamInterval = setInterval(triggerSimulation, 4000);
        if (btn) {
            btn.innerText = "⏸ Streaming";
            btn.classList.remove("btn-outline-sm");
            btn.classList.add("btn-primary-sm");
        }
    }
}

// Filters & Search
function filterDustbins() {
    const searchInput = document.getElementById("searchInput");
    const typeFilter = document.getElementById("typeFilter");

    if (searchInput) currentFilter.search = searchInput.value;
    if (typeFilter) currentFilter.type = typeFilter.value;

    renderDustbinGrid();
}

function setFilter(type, value, element) {
    if (type === "status") {
        currentFilter.status = value;
        document.querySelectorAll(".filter-btn").forEach(btn => btn.classList.remove("active"));
        if (element) element.classList.add("active");
    }
    renderDustbinGrid();
}

// Modal Handlers
function openAddNodeModal() {
    const modal = document.getElementById("addNodeModal");
    if (modal) modal.classList.add("active");
}

function closeAddNodeModal() {
    const modal = document.getElementById("addNodeModal");
    if (modal) modal.classList.remove("active");
}

async function handleAddNodeSubmit(event) {
    event.preventDefault();
    const location = document.getElementById("nodeLocation").value;
    const bin_type = document.getElementById("nodeType").value;
    const capacity_liters = document.getElementById("nodeCapacity").value;
    const latitude = document.getElementById("nodeLat").value;
    const longitude = document.getElementById("nodeLng").value;
    const waste_level = document.getElementById("nodeInitialFill").value;

    try {
        const response = await fetch("/api/dustbin/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ location, bin_type, capacity_liters, latitude, longitude, waste_level })
        });
        const data = await response.json();

        if (data.success) {
            closeAddNodeModal();
            document.getElementById("addNodeForm").reset();
            await loadDustbinData();
        } else {
            alert(data.message || "Failed to register node.");
        }
    } catch (e) {
        console.error("Add Node Error:", e);
    }
}

function printRouteSheet() {
    window.print();
}

// Initialization on DOM Load
document.addEventListener("DOMContentLoaded", () => {
    loadDustbinData();
    setInterval(loadDustbinData, 6000);
});
