// Utility: Display JSON output in the log box
function displayOutput(data) {
    const outputEl = document.getElementById("output");
    outputEl.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    outputEl.scrollTop = outputEl.scrollHeight;
}

// 1️⃣ UAV Registration
async function registerUAV() {
    const uavId = document.getElementById("uavIdInput").value.trim();
    if (!uavId) {
        alert("Please enter a UAV ID.");
        return;
    }

    const response = await fetch("/register_uav", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uav_id: uavId }),
    });

    const result = await response.json();
    displayOutput(result);

    if (result.status === "success") {
        document.getElementById("uavIdAuth").value = result.uav_id;
        document.getElementById("uavToken").value = result.token;
    }
}

// 2️⃣ Upload File
async function uploadFile() {
    const uavId = document.getElementById("uavIdAuth").value;
    const token = document.getElementById("uavToken").value;
    const fileInput = document.getElementById("fileInput");

    if (!uavId || !token || fileInput.files.length === 0) {
        alert("Please register UAV and select a file.");
        return;
    }

    const formData = new FormData();
    formData.append("uav_id", uavId);
    formData.append("token", token);
    formData.append("dataset", fileInput.files[0]);

    const response = await fetch("/upload_dataset", { method: "POST", body: formData });
    const result = await response.json();
    displayOutput(result);

    if (result.status === "success") fetchAndDisplayLedger();
}
async function fetchUavData() {
    const uavId = document.getElementById("retrieveUavId").value;
    const outputEl = document.getElementById("output");

    if (!uavId.trim()) {
        alert("Please enter a UAV ID");
        return;
    }

    outputEl.textContent = "🔍 Fetching dataset...";

    try {
        const res = await fetch(`/get_dataset_by_uav?uav_id=${uavId}`);
        const result = await res.json();

        if (result.status === "success") {
            outputEl.textContent =
                `✅ Dataset found for UAV: ${uavId}\n\n` +
                JSON.stringify(result.uploaded_files, null, 2);
        } else {
            outputEl.textContent = `❌ ${result.message}`;
        }
    } catch (err) {
        outputEl.textContent = "⚠️ Error retrieving dataset: " + err.message;
    }
}

// 3️⃣ Predict Fertilizer Using Uploaded JSON
async function predictFromUploadedFile() {
    const outputEl = document.getElementById("output");

    try {
        const res = await fetch("/get_uploaded_data");
        const allFiles = await res.json();

        if (!allFiles.length) {
            outputEl.textContent = "❌ No uploaded data found.";
            return;
        }

        const fileData = allFiles[allFiles.length - 1].data;

        let finalText = "✅ Predictions:\n\n";

        for (let row of fileData) {
            // REMOVE NaN completely
            Object.keys(row).forEach(k => {
                if (row[k] === null || Number.isNaN(row[k])) delete row[k];
            });

            const res2 = await fetch("/predict_fertilizer", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(row)
            });

            const out = await res2.json();

            finalText += `Crop: ${row["Crop Type"]} → ${out.predicted_fertilizer}\n`;
        }

        outputEl.textContent = finalText;

    } catch (err) {
        outputEl.textContent = "❌ Prediction error: " + err.message;
    }
}

// 4️⃣ Fetch Ledger Data
async function fetchAndDisplayLedger() {
    try {
        const response = await fetch("/get_ledger", { cache: "no-cache" });
        const ledger = await response.json();
        const container = document.getElementById("ledger-display-container");

        container.innerHTML = "";
        if (ledger.length === 0) {
            container.innerHTML = "<p>No blocks in ledger. Upload a dataset to start.</p>";
            return;
        }

        ledger.slice().reverse().forEach((block) => {
            const blockEl = document.createElement("div");
            blockEl.className = "ledger-block";
            blockEl.innerHTML = `
                <div class="block-header">
                    <div class="block-index">Block #${block.block_id}</div>
                    <div class="block-uploader">UAV: ${block.uploader_uav}</div>
                </div>
                <div class="block-content">
                    <strong>File Name:</strong> ${block.filename}<br>
                    <strong>File Size:</strong> ${block.size_bytes} bytes
                </div>
                <div class="hash-display">
                    <strong>File Hash:</strong> <span>${block.file_hash}</span>
                </div>
            `;
            container.appendChild(blockEl);
        });
    } catch (err) {
        console.error("Failed to fetch ledger:", err);
        document.getElementById("ledger-display-container").innerHTML = "<p>Error loading ledger data.</p>";
    }
}
function initMap() {
    const map = L.map("map").setView([20.5937, 78.9629], 5);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
    }).addTo(map);

    // Draw control
    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);

    const drawControl = new L.Control.Draw({
        draw: {
            polyline: false,
            circle: false,
            marker: false,
            rectangle: false,
            circlemarker: false,
            polygon: true
        },
        edit: {
            featureGroup: drawnItems
        }
    });

    map.addControl(drawControl);

    // WHEN USER FINISHES DRAWING
    map.on(L.Draw.Event.CREATED, async function (event) {
    const layer = event.layer;
    drawnItems.addLayer(layer);

    const coords = layer.getLatLngs()[0].map(pt => [pt.lat, pt.lng]);

    // STORE polygon
    const res = await fetch("/store_polygon", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ coords })
    });

    const poly = await res.json();
    const polygonId = poly.polygon_id;

    // NOW GET DRONES INSIDE THIS POLYGON
    const res2 = await fetch(`/drones_in_polygon?polygon_id=${polygonId}`);
    const output = await res2.json();

    document.getElementById("output").textContent =
        JSON.stringify(output, null, 2);
});

}


// Auto-load ledger when page opens
document.addEventListener("DOMContentLoaded", fetchAndDisplayLedger);
