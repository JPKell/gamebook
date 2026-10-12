/**
 * Frontend application.
 *
 * Vanilla JavaScript client for the Gamebook Authoring Tool.
 * Handles API calls, sidebar tree rendering, canvas drawing,
 * and modal interactions.
 *
 * Architecture:
 *   - appState: single source of truth for all data.
 *   - render*(): functions that derive UI from appState.
 *   - api: helper for fetch calls to the FastAPI backend.
 *   - canvas: Canvas API drawing for the graph view.
 *
 * Future phases (7+):
 *   - Story generation triggers, playthrough tracking,
 *     and assembly output are not implemented yet.
 */

const appState = {
    seriesId: null,
    bookId: null,
    series: null,
    book: null,
    nodes: [],
    acts: [],
    choices: [],
    sharedLocations: [],
    sharedItems: [],
    sharedEncounters: [],
    bookLocations: [],
    bookItems: [],
    bookEncounters: [],
    selectedNodeId: null,
    editingNodeId: null,
    connectSourceId: null,
    canvasOffsetX: 0,
    canvasOffsetY: 0,
    canvasScale: 1,
    draggingNode: null,
    dragStartX: 0,
    dragStartY: 0,
    panStartX: 0,
    panStartY: 0,
    isPanning: false,
    validationIssues: [],
};

const API = {
    base: "/api",

    async get(path) {
        const res = await fetch(`${this.base}${path}`);
        if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
        return res.json();
    },

    async post(path, body) {
        const res = await fetch(`${this.base}${path}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || res.statusText);
        }
        return res.json();
    },

    async put(path, body) {
        const res = await fetch(`${this.base}${path}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || res.statusText);
        }
        return res.json();
    },

    async delete(path) {
        const res = await fetch(`${this.base}${path}`, { method: "DELETE" });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || res.statusText);
        }
        return res.json();
    },
};

// --- API wrappers ---

async function loadSeriesList() {
    const list = await API.get("/series/");
    renderSidebar(list);
}

async function loadSeries(seriesId) {
    appState.seriesId = seriesId;
    const data = await API.get(`/series/${seriesId}`);
    appState.series = data;
    renderSidebar([data]);
    setStatus(`Loaded series: ${data.title}`);
}

async function createSeries(title, description, tone, worldGuidelines) {
    const data = await API.post("/series/", { title, description, tone, worldGuidelines });
    appState.seriesId = data.id;
    await loadSeriesList();
    setStatus(`Created series: ${title}`);
    return data;
}

async function loadBook(bookId) {
    appState.bookId = bookId;
    const data = await API.get(`/books/${bookId}`);
    appState.book = data;
    appState.nodes = data.nodes || [];
    appState.acts = data.acts || [];
    appState.choices = data.choices || [];
    appState.sharedLocations = data.sharedLocations || [];
    appState.sharedItems = data.sharedItems || [];
    appState.sharedEncounters = data.sharedEncounters || [];
    appState.bookLocations = data.bookLocations || [];
    appState.bookItems = data.bookItems || [];
    appState.bookEncounters = data.bookEncounters || [];
    renderSidebar();
    renderEntityPanel("shared");
    setStatus(`Loaded book: ${data.title}`);
}

async function createBook(seriesId, title, number) {
    const data = await API.post(`/series/${seriesId}/books`, { title, number });
    await loadBook(data.id);
    setStatus(`Created book: ${title}`);
    return data;
}

async function createNode(bookId, opts = {}) {
    const data = await API.post(`/books/${bookId}/nodes`, {
        title: opts.title || "New Node",
        actId: opts.actId || null,
        type: opts.type || "beat",
        x: opts.x || 0,
        y: opts.y || 0,
    });
    appState.nodes.push(data);
    renderCanvas();
    setStatus(`Created node: ${data.title}`);
    return data;
}

async function updateNode(nodeId, updates) {
    const data = await API.put(`/books/${appState.bookId}/nodes/${nodeId}`, updates);
    const idx = appState.nodes.findIndex(n => n.id === nodeId);
    if (idx >= 0) Object.assign(appState.nodes[idx], data);
    renderCanvas();
}

async function deleteNode(nodeId) {
    await API.delete(`/books/${appState.bookId}/nodes/${nodeId}`);
    appState.nodes = appState.nodes.filter(n => n.id !== nodeId);
    appState.choices = appState.choices.filter(c =>
        c.sourceNodeId !== nodeId && c.targetId !== nodeId
    );
    renderCanvas();
    setStatus("Node deleted.");
}

async function addChoice(sourceNodeId, targetId, text) {
    const data = await API.post(
        `/books/${appState.bookId}/nodes/${sourceNodeId}/choices`,
        { targetId, text }
    );
    appState.choices.push(data);
    renderCanvas();
    setStatus(`Connected: ${text}`);
}

async function deleteChoice(choiceId) {
    await API.delete(`/books/${appState.bookId}/choices/${choiceId}`);
    appState.choices = appState.choices.filter(c => c.id !== choiceId);
    renderCanvas();
    setStatus("Choice deleted.");
}

async function addAct(bookId, title) {
    const data = await API.post(`/books/${bookId}/acts`, { title });
    await loadBook(bookId);
    setStatus(`Added act: ${title}`);
    return data;
}

// --- UI rendering ---

function renderSidebar(seriesList) {
    const container = document.getElementById("sidebar-tree");
    if (!seriesList || seriesList.length === 0) {
        container.innerHTML = '<p class="sidebar-placeholder">No series loaded.</p>';
        return;
    }

    let html = "";
    for (const series of seriesList) {
        const active = series.id === appState.seriesId ? ' class="active"' : "";
        html += `<div class="tree-item${active}" data-series-id="${series.id}">`;
        html += `<span class="tree-label" data-action="select-series">📚 ${series.title}</span>`;
        html += `<div class="tree-children">`;
        html += `<button class="btn-small" data-action="new-book" data-series-id="${series.id}">+ Book</button>`;

        if (series.books) {
            for (const book of series.books) {
                const bookActive = book.id === appState.bookId ? ' class="active"' : "";
                html += `<div class="tree-item${bookActive}">`;
                html += `<span class="tree-label" data-action="select-book" data-book-id="${book.id}">📖 ${book.title}</span>`;
                html += `<div class="tree-children">`;
                html += `<button class="btn-small" data-action="new-act" data-book-id="${book.id}">+ Act</button>`;

                // Render acts and nodes for this book
                if (appState.bookId === book.id) {
                    const acts = appState.acts || [];
                    for (const act of acts.sort((a, b) => a.order - b.order)) {
                        html += `<div class="tree-act">`;
                        html += `<span class="tree-label">Act ${act.order}: ${act.title}</span>`;
                        html += `<button class="btn-small" data-action="new-node" data-act-id="${act.id}">+ Node</button>`;
                        // Render nodes in this act
                        const actNodes = (appState.nodes || []).filter(n => n.actId === act.id);
                        for (const node of actNodes) {
                            const typeIcon = { entry: "🟢", beat: "⬜", exit: "🟠", ending: "🔴" }[node.type] || "⬜";
                            const nodeActive = node.id === appState.selectedNodeId ? ' class="active"' : "";
                            html += `<span class="tree-node${nodeActive}" data-action="select-node" data-node-id="${node.id}">${typeIcon} ${node.title}</span>`;
                        }
                        html += `</div>`;
                    }
                }
                html += `</div>`;
                html += `</div>`;
            }
        }
        html += `</div>`;
        html += `</div>`;
    }
    container.innerHTML = html;
}

function renderEntityPanel(tab) {
    const container = document.getElementById("entity-list");
    const locations = tab === "shared"
        ? appState.sharedLocations : appState.bookLocations;
    const items = tab === "shared"
        ? appState.sharedItems : appState.bookItems;
    const encounters = tab === "shared"
        ? appState.sharedEncounters : appState.bookEncounters;

    let html = "";

    html += `<div class="entity-group">`;
    html += `<div class="entity-group-header">`;
    html += `<span>Locations (${locations.length})</span>`;
    html += `<button class="btn-small" data-action="new-entity" data-type="location" data-scope="${tab}">+</button>`;
    html += `</div>`;
    for (const loc of locations) {
        html += `<span class="entity-item" data-id="${loc.id}" data-type="location">${loc.name}</span>`;
    }
    html += `</div>`;

    html += `<div class="entity-group">`;
    html += `<div class="entity-group-header">`;
    html += `<span>Items (${items.length})</span>`;
    html += `<button class="btn-small" data-action="new-entity" data-type="item" data-scope="${tab}">+</button>`;
    html += `</div>`;
    for (const item of items) {
        html += `<span class="entity-item" data-id="${item.id}" data-type="item">${item.name}</span>`;
    }
    html += `</div>`;

    html += `<div class="entity-group">`;
    html += `<div class="entity-group-header">`;
    html += `<span>Encounters (${encounters.length})</span>`;
    html += `<button class="btn-small" data-action="new-entity" data-type="encounter" data-scope="${tab}">+</button>`;
    html += `</div>`;
    for (const enc of encounters) {
        html += `<span class="entity-item" data-id="${enc.id}" data-type="encounter">${enc.name}</span>`;
    }
    html += `</div>`;

    container.innerHTML = html;
}

// --- Canvas drawing ---

function renderCanvas() {
    const canvas = document.getElementById("canvas");
    const overlay = document.getElementById("canvas-overlay");

    if (!appState.bookId) {
        canvas.style.display = "none";
        overlay.style.display = "flex";
        overlay.querySelector(".canvas-placeholder").textContent = "Select a book to begin editing.";
        return;
    }

    canvas.style.display = "block";
    overlay.style.display = "none";

    const ctx = canvas.getContext("2d");
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw background grid
    ctx.save();
    ctx.translate(appState.canvasOffsetX, appState.canvasOffsetY);
    ctx.scale(appState.canvasScale, appState.canvasScale);

    // Grid
    ctx.strokeStyle = "#333";
    ctx.lineWidth = 0.5;
    const gridSize = 50;
    const startX = -appState.canvasOffsetX / appState.canvasScale;
    const startY = -appState.canvasOffsetY / appState.canvasScale;
    const endX = (canvas.width - appState.canvasOffsetX) / appState.canvasScale;
    const endY = (canvas.height - appState.canvasOffsetY) / appState.canvasScale;

    for (let x = Math.floor(startX / gridSize) * gridSize; x <= endX; x += gridSize) {
        ctx.beginPath(); ctx.moveTo(x, startY); ctx.lineTo(x, endY); ctx.stroke();
    }
    for (let y = Math.floor(startY / gridSize) * gridSize; y <= endY; y += gridSize) {
        ctx.beginPath(); ctx.moveTo(startX, y); ctx.lineTo(endX, y); ctx.stroke();
    }

    // Draw choices (edges)
    ctx.strokeStyle = "#555";
    ctx.lineWidth = 2;
    for (const choice of appState.choices) {
        const src = appState.nodes.find(n => n.id === choice.sourceNodeId);
        const tgt = appState.nodes.find(n => n.id === choice.targetId);
        if (!src || !tgt) continue;

        ctx.beginPath();
        ctx.moveTo(src.x + 60, src.y);
        ctx.lineTo(tgt.x, tgt.y);
        ctx.stroke();

        // Arrow head
        const angle = Math.atan2(tgt.y - (src.y), tgt.x - (src.x + 60));
        ctx.beginPath();
        ctx.moveTo(tgt.x, tgt.y);
        ctx.lineTo(tgt.x - 10 * Math.cos(angle - 0.4), tgt.y - 10 * Math.sin(angle - 0.4));
        ctx.moveTo(tgt.x, tgt.y);
        ctx.lineTo(tgt.x - 10 * Math.cos(angle + 0.4), tgt.y - 10 * Math.sin(angle + 0.4));
        ctx.stroke();
    }

    // Draw nodes
    for (const node of appState.nodes) {
        const isSelected = node.id === appState.selectedNodeId;
        const colors = {
            entry: { border: "#4caf50", bg: "#1a3a1a" },
            beat: { border: "#555", bg: "#1a1a2a" },
            exit: { border: "#ff9800", bg: "#3a2a0a" },
            ending: { border: "#f44336", bg: "#3a1a1a" },
        };
        const c = colors[node.type] || colors.beat;

        ctx.fillStyle = c.bg;
        ctx.strokeStyle = c.border;
        ctx.lineWidth = isSelected ? 3 : 1.5;
        roundRect(ctx, node.x, node.y, 120, 50, 8);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#fff";
        ctx.font = "13px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const title = node.title.length > 14 ? node.title.slice(0, 13) + "…" : node.title;
        ctx.fillText(title, node.x + 60, node.y + 25);
    }

    ctx.restore();

    // Draw validation issues in status bar
    if (appState.validationIssues.length > 0) {
        setStatus(`${appState.validationIssues.length} validation issue(s).`);
    }
}

function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

// --- Modal management ---

function openModal(id) {
    document.getElementById(id).classList.remove("hidden");
}
function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
}

// --- Status bar ---

function setStatus(msg) {
    document.getElementById("status-message").textContent = msg;
}

// --- Event delegation ---

document.addEventListener("DOMContentLoaded", () => {
    // Load series list on startup
    loadSeriesList();

    // Canvas click handler (select node, drag, pan)
    const canvas = document.getElementById("canvas");

    canvas.addEventListener("mousedown", (e) => {
        const rect = canvas.getBoundingClientRect();
        const mx = (e.clientX - rect.left - appState.canvasOffsetX) / appState.canvasScale;
        const my = (e.clientY - rect.top - appState.canvasOffsetY) / appState.canvasScale;

        // Check if clicking on a node
        let clickedNode = null;
        for (const node of appState.nodes) {
            if (mx >= node.x && mx <= node.x + 120 && my >= node.y && my <= node.y + 50) {
                clickedNode = node;
                break;
            }
        }

        if (clickedNode) {
            appState.selectedNodeId = clickedNode.id;
            appState.draggingNode = clickedNode;
            appState.dragStartX = mx - clickedNode.x;
            appState.dragStartY = my - clickedNode.y;
            renderCanvas();
            return;
        }

        // Pan
        appState.isPanning = true;
        appState.panStartX = e.clientX - appState.canvasOffsetX;
        appState.panStartY = e.clientY - appState.canvasOffsetY;
    });

    canvas.addEventListener("mousemove", (e) => {
        if (appState.draggingNode) {
            const rect = canvas.getBoundingClientRect();
            const mx = (e.clientX - rect.left - appState.canvasOffsetX) / appState.canvasScale;
            const my = (e.clientY - rect.top - appState.canvasOffsetY) / appState.canvasScale;
            appState.draggingNode.x = mx - appState.dragStartX;
            appState.draggingNode.y = my - appState.dragStartY;
            renderCanvas();
            return;
        }
        if (appState.isPanning) {
            appState.canvasOffsetX = e.clientX - appState.panStartX;
            appState.canvasOffsetY = e.clientY - appState.panStartY;
            renderCanvas();
        }
    });

    canvas.addEventListener("mouseup", (e) => {
        if (appState.draggingNode) {
            // Save the new position
            updateNode(appState.draggingNode.id, {
                x: appState.draggingNode.x,
                y: appState.draggingNode.y,
            });
            appState.draggingNode = null;
        }
        appState.isPanning = false;
    });

    canvas.addEventListener("dblclick", (e) => {
        const rect = canvas.getBoundingClientRect();
        const mx = (e.clientX - rect.left - appState.canvasOffsetX) / appState.canvasScale;
        const my = (e.clientY - rect.top - appState.canvasOffsetY) / appState.canvasScale;

        for (const node of appState.nodes) {
            if (mx >= node.x && mx <= node.x + 120 && my >= node.y && my <= node.y + 50) {
                openEditModal(node);
                return;
            }
        }
    });

    canvas.addEventListener("wheel", (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        appState.canvasScale = Math.max(0.2, Math.min(3, appState.canvasScale * delta));
        renderCanvas();
    });

    // Global event delegation for sidebar, modals, toolbar
    document.addEventListener("click", async (e) => {
        const target = e.target.closest("[data-action]");
        if (!target) return;

        const action = target.dataset.action;
        const bookId = target.dataset.bookId;
        const seriesId = target.dataset.seriesId;
        const actId = target.dataset.actId;
        const nodeId = target.dataset.nodeId;
        const entityType = target.dataset.type;
        const scope = target.dataset.scope;

        // Toolbar actions
        if (action === "new-series") {
            openModal("modal-new-series");
            return;
        }
        if (action === "new-book") {
            openModal("modal-new-book");
            document.getElementById("modal-new-book-submit").dataset.seriesId = seriesId;
            return;
        }
        if (action === "new-act") {
            const title = prompt(`New act title for book ${appState.bookId}:`);
            if (title) await addAct(bookId, title);
            return;
        }
        if (action === "new-node") {
            const title = prompt("Node title:", "New Node");
            if (title) {
                await createNode(appState.bookId, {
                    actId: actId || null,
                    type: "beat",
                    x: 200 + Math.random() * 200,
                    y: 100 + Math.random() * 200,
                });
            }
            return;
        }
        if (action === "select-series") {
            await loadSeries(seriesId);
            return;
        }
        if (action === "select-book") {
            await loadBook(bookId);
            return;
        }
        if (action === "select-node") {
            appState.selectedNodeId = nodeId;
            renderCanvas();
            return;
        }
        if (action === "new-entity") {
            document.getElementById("modal-new-entity-title").textContent =
                `New ${entityType.charAt(0).toUpperCase() + entityType.slice(1)}`;
            document.getElementById("modal-new-entity-submit").dataset.type = entityType;
            document.getElementById("modal-new-entity-submit").dataset.scope = scope;
            openModal("modal-new-entity");
            return;
        }
    });

    // Modal cancel buttons
    document.querySelectorAll(".modal-cancel").forEach(btn => {
        btn.addEventListener("click", () => {
            btn.closest(".modal").classList.add("hidden");
        });
    });

    // Connect modal
    document.getElementById("modal-connect-submit").addEventListener("click", async () => {
        const text = document.getElementById("modal-connect-text").value;
        const targetId = document.getElementById("modal-connect-target").value;
        if (text && targetId && appState.connectSourceId) {
            await addChoice(appState.connectSourceId, targetId, text);
            closeModal("modal-connect");
        }
    });

    document.getElementById("modal-connect-back").addEventListener("click", async () => {
        const text = document.getElementById("modal-connect-text").value;
        const targetId = document.getElementById("modal-connect-target").value;
        if (text && targetId && appState.connectSourceId) {
            await addChoice(appState.connectSourceId, targetId, text + " (back)");
            closeModal("modal-connect");
        }
    });

    // New book modal
    document.getElementById("modal-new-book-submit").addEventListener("click", async () => {
        const title = document.getElementById("modal-new-book-title").value;
        const number = document.getElementById("modal-new-book-number").value;
        if (title) {
            const seriesId = document.getElementById("modal-new-book-submit").dataset.seriesId;
            await createBook(seriesId, title, number || null);
            closeModal("modal-new-book");
            document.getElementById("modal-new-book-title").value = "";
        }
    });

    // New series modal
    document.getElementById("modal-new-series-submit").addEventListener("click", async () => {
        const title = document.getElementById("modal-new-series-title").value;
        const desc = document.getElementById("modal-new-series-description").value;
        const tone = document.getElementById("modal-new-series-tone").value;
        const guidelines = document.getElementById("modal-new-series-guidelines").value;
        if (title) {
            await createSeries(title, desc, tone, guidelines);
            closeModal("modal-new-series");
            document.getElementById("modal-new-series-title").value = "";
            document.getElementById("modal-new-series-description").value = "";
            document.getElementById("modal-new-series-tone").value = "";
            document.getElementById("modal-new-series-guidelines").value = "";
        }
    });

    // New entity modal
    document.getElementById("modal-new-entity-submit").addEventListener("click", async () => {
        const name = document.getElementById("modal-new-entity-name").value;
        const desc = document.getElementById("modal-new-entity-desc").value;
        const type = document.getElementById("modal-new-entity-submit").dataset.type;
        const scope = document.getElementById("modal-new-entity-submit").dataset.scope;
        if (name && appState.bookId) {
            const seriesPath = scope === "series" ? "series" : "books";
            await API.post(
                `/${seriesPath}/${scope === "series" ? appState.seriesId : appState.bookId}/${type}s`,
                { name, description: desc }
            );
            closeModal("modal-new-entity");
            await loadBook(appState.bookId);
        }
    });

    // Entity item click (select for node assignment)
    document.addEventListener("click", (e) => {
        const item = e.target.closest(".entity-item");
        if (!item) return;
        if (appState.editingNodeId) {
            // This would populate the entity field in the edit modal
            // Simplified for now
            setStatus(`Selected ${item.dataset.type}: ${item.textContent}`);
        }
    });

    // Tab switching for entity panel
    document.querySelectorAll(".tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            renderEntityPanel(tab.dataset.tab);
        });
    });
});

// --- Open edit modal for a node ---

async function openEditModal(node) {
    appState.editingNodeId = node.id;

    document.getElementById("modal-edit-title").value = node.title || "";
    document.getElementById("modal-edit-description").value = node.description || "";
    document.getElementById("modal-edit-type").value = node.type || "beat";

    // Populate act dropdown
    const actSelect = document.getElementById("modal-edit-act");
    actSelect.innerHTML = '<option value="">— None —</option>';
    for (const act of (appState.acts || []).sort((a, b) => a.order - b.order)) {
        const sel = act.id === node.actId ? " selected" : "";
        actSelect.innerHTML += `<option value="${act.id}"${sel}>Act ${act.order}: ${act.title}</option>`;
    }

    // Populate location dropdown
    const locSelect = document.getElementById("modal-edit-location");
    locSelect.innerHTML = '<option value="">— None —</option>';
    const allLocations = [
        ...appState.sharedLocations.map(l => ({ ...l, scope: "(shared)" })),
        ...appState.bookLocations.map(l => ({ ...l, scope: "(this book)" })),
    ];
    for (const loc of allLocations) {
        const sel = loc.id === node.locationId ? " selected" : "";
        locSelect.innerHTML += `<option value="${loc.id}"${sel}>${loc.name} ${loc.scope}</option>`;
    }

    // Populate choice target dropdown
    const targetSelect = document.getElementById("modal-connect-target");
    targetSelect.innerHTML = "";
    for (const n of appState.nodes) {
        if (n.id !== node.id) {
            targetSelect.innerHTML += `<option value="${n.id}">${n.title}</option>`;
        }
    }

    openModal("modal-edit");

    // Bind save button
    document.getElementById("modal-edit-submit").onclick = async () => {
        const updates = {
            title: document.getElementById("modal-edit-title").value,
            description: document.getElementById("modal-edit-description").value,
            type: document.getElementById("modal-edit-type").value,
            actId: document.getElementById("modal-edit-act").value || null,
            locationId: document.getElementById("modal-edit-location").value || null,
        };
        await updateNode(node.id, updates);
        closeModal("modal-edit");
    };

    // Bind delete button
    document.getElementById("modal-edit-delete").onclick = async () => {
        if (confirm(`Delete node "${node.title}"?`)) {
            await deleteNode(node.id);
            closeModal("modal-edit");
        }
    };

    // Bind context menu (right-click on node)
    canvas.addEventListener("contextmenu", (e) => {
        const rect = canvas.getBoundingClientRect();
        const mx = (e.clientX - rect.left - appState.canvasOffsetX) / appState.canvasScale;
        const my = (e.clientY - rect.top - appState.canvasOffsetY) / appState.canvasScale;

        for (const n of appState.nodes) {
            if (mx >= n.x && mx <= n.x + 120 && my >= n.y && my <= n.y + 50) {
                appState.connectSourceId = n.id;
                document.getElementById("modal-connect-title").textContent = `Connect from: "${n.title}"`;
                document.getElementById("modal-connect-text").value = "";
                // Repopulate target dropdown
                const targetSelect = document.getElementById("modal-connect-target");
                targetSelect.innerHTML = "";
                for (const t of appState.nodes) {
                    if (t.id !== n.id) {
                        targetSelect.innerHTML += `<option value="${t.id}">${t.title}</option>`;
                    }
                }
                openModal("modal-connect");
                e.preventDefault();
                return;
            }
        }
    });
}
