async function loadDustbinData() {
    try {
        const response = await fetch("/api/dustbins");
        const data = await response.json();

        console.log("Dustbin Data:", data);

        let normalCount = 0;
        let warningCount = 0;
        let fullCount = 0;

        const alertsContainer = document.getElementById("alertsContainer");

        if (alertsContainer) {
            alertsContainer.innerHTML = "";
        }

        data.dustbins.forEach((dustbin, index) => {

            const number = index + 1;

            const bar = document.getElementById("bar" + number);
            const percentage = document.getElementById("percentage" + number);

            const wasteLevel = document.getElementById(
                "wasteLevel" + dustbin.id
            );

            const status = document.getElementById(
                "status" + dustbin.id
            );

            const collection = document.getElementById(
                "collection" + dustbin.id
            );

            if (bar && percentage) {
                bar.style.width = dustbin.waste_level + "%";
                percentage.textContent = dustbin.waste_level + "%";
            }

            if (wasteLevel) {
                wasteLevel.textContent = dustbin.waste_level + "%";
            }

            if (status) {

                if (dustbin.status === "Normal") {
                    status.textContent = "🟢 Normal";
                }

                else if (dustbin.status === "Warning") {
                    status.textContent = "🟡 Warning";
                }

                else {
                    status.textContent = "🔴 Full";
                }
            }

            if (collection) {
                collection.textContent = dustbin.collection_status;
            }

            if (dustbin.status === "Normal") {
                normalCount++;
            }

            else if (dustbin.status === "Warning") {
                warningCount++;
            }

            else if (dustbin.status === "Full") {
                fullCount++;
            }

            if (alertsContainer) {

                if (dustbin.status === "Full") {

                    alertsContainer.innerHTML += `
                        <div class="alert full-alert">
                            🚨 <strong>Waste Collection Alert!</strong>
                            Dustbin ${dustbin.id} - ${dustbin.location}
                            is Full (${dustbin.waste_level}%).
                        </div>
                    `;
                }

                else if (dustbin.status === "Warning") {

                    alertsContainer.innerHTML += `
                        <div class="alert warning-alert">
                            ⚠️ <strong>Warning!</strong>
                            Dustbin ${dustbin.id} - ${dustbin.location}
                            is almost full (${dustbin.waste_level}%).
                        </div>
                    `;
                }
            }
        });

        const normalElement = document.getElementById("normalCount");
        const warningElement = document.getElementById("warningCount");
        const fullElement = document.getElementById("fullCount");
        const totalElement = document.getElementById("totalDustbins");

        if (normalElement) {
            normalElement.textContent = normalCount;
        }

        if (warningElement) {
            warningElement.textContent = warningCount;
        }

        if (fullElement) {
            fullElement.textContent = fullCount;
        }

        if (totalElement) {
            totalElement.textContent = data.dustbins.length;
        }

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

        alert(data.message);

        await loadDustbinData();

        window.location.reload();

    } catch (error) {

        console.error("Collection Error:", error);

        alert("Something went wrong while collecting the dustbin.");
    }
}


loadDustbinData();

setInterval(loadDustbinData, 5000);