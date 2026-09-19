async function loadDustbinData() {
    try {
        const response = await fetch("/api/dustbins");
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        let normalCount = 0;
        let warningCount = 0;
        let fullCount = 0;

        const alertsContainer = document.getElementById("alertsContainer");
        const chartContainer = document.querySelector(".chart-container");
        const dustbinContainer = document.getElementById("dustbinContainer");

        if (alertsContainer) {
            alertsContainer.innerHTML = "";
        }

        // Render chart bars dynamically
        if (chartContainer) {
            chartContainer.innerHTML = data.dustbins.map(dustbin => {
                let fillClass = "bar-fill-normal";
                if (dustbin.status === "Warning") fillClass = "bar-fill-warning";
                if (dustbin.status === "Full") fillClass = "bar-fill-full";

                return `
                    <div class="chart-row">
                        <div class="chart-label">
                            <span>Dustbin ${dustbin.id} - ${dustbin.location}</span>
                            <span class="percentage">${dustbin.waste_level}%</span>
                        </div>
                        <div class="bar-background">
                            <div class="bar-fill ${fillClass}" id="bar${dustbin.id}" style="width: ${dustbin.waste_level}%"></div>
                        </div>
                    </div>
                `;
            }).join("");
        }

        // Render dustbin detail cards dynamically
        if (dustbinContainer) {
            dustbinContainer.innerHTML = data.dustbins.map(dustbin => {
                let statusBadge = "🟢 Normal";
                if (dustbin.status === "Warning") statusBadge = "🟡 Warning";
                if (dustbin.status === "Full") statusBadge = "🔴 Full";

                const isPending = dustbin.collection_status === "Pending";
                const buttonHtml = isPending 
                    ? `<button onclick="collectDustbin(${dustbin.id})">🚮 Mark as Collected</button>`
                    : `<span style="color: #34d399; font-weight: 600;">✅ Cleaned</span>`;

                return `
                    <div class="dustbin">
                        <div>
                            <h3>Dustbin ${dustbin.id} - ${dustbin.location}</h3>
                            <p>Waste Level: <strong id="wasteLevel${dustbin.id}">${dustbin.waste_level}%</strong></p>
                            <p>Status: <strong id="status${dustbin.id}">${statusBadge}</strong></p>
                            <p>Collection: <strong id="collection${dustbin.id}">${dustbin.collection_status}</strong></p>
                        </div>
                        <div style="margin-top: 15px;">
                            ${buttonHtml}
                        </div>
                    </div>
                `;
            }).join("");
        }

        // Process alerts & counts
        data.dustbins.forEach(dustbin => {
            if (dustbin.status === "Normal") normalCount++;
            else if (dustbin.status === "Warning") warningCount++;
            else if (dustbin.status === "Full") fullCount++;

            if (alertsContainer) {
                if (dustbin.status === "Full") {
                    alertsContainer.innerHTML += `
                        <div class="alert full-alert">
                            🚨 <strong>Waste Collection Alert!</strong> Dustbin ${dustbin.id} - ${dustbin.location} is Full (${dustbin.waste_level}%). Immediate pickup required!
                        </div>
                    `;
                } else if (dustbin.status === "Warning") {
                    alertsContainer.innerHTML += `
                        <div class="alert warning-alert">
                            ⚠️ <strong>Warning!</strong> Dustbin ${dustbin.id} - ${dustbin.location} is approaching capacity (${dustbin.waste_level}%).
                        </div>
                    `;
                }
            }
        });

        // Update total counter cards
        const normalElement = document.getElementById("normalCount");
        const warningElement = document.getElementById("warningCount");
        const fullElement = document.getElementById("fullCount");
        const totalElement = document.getElementById("totalDustbins");

        if (normalElement) normalElement.textContent = normalCount;
        if (warningElement) warningElement.textContent = warningCount;
        if (fullElement) fullElement.textContent = fullCount;
        if (totalElement) totalElement.textContent = data.dustbins.length;

    } catch (error) {
        console.error("Error loading dustbin data:", error);
    }
}


async function collectDustbin(dustbinId) {
    try {
        const response = await fetch("/collect/" + dustbinId, {
            method: "POST"
        });

        const data = await response.json();
        
        // Instant refresh
        await loadDustbinData();

    } catch (error) {
        console.error("Collection Error:", error);
        alert("Something went wrong while marking dustbin as collected.");
    }
}


async function triggerSimulation() {
    try {
        const simBtn = document.getElementById("simBtn");
        if (simBtn) {
            simBtn.disabled = true;
            simBtn.innerText = "⏳ Simulating...";
        }

        const response = await fetch("/api/simulate", {
            method: "POST"
        });
        const data = await response.json();
        
        await loadDustbinData();

        if (simBtn) {
            simBtn.disabled = false;
            simBtn.innerText = "⚡ Simulate Telemetry";
        }
    } catch (error) {
        console.error("Simulation Error:", error);
        alert("Simulation request failed.");
    }
}

// Initial load
document.addEventListener("DOMContentLoaded", () => {
    loadDustbinData();
    setInterval(loadDustbinData, 5000);
});
