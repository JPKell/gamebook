/**
 * Canvas rendering and interaction for the Gamebook Authoring Tool.
 *
 * Implements Phase 2 of the work plan:
 *   - Canvas API rendering of nodes (rounded rects, color-coded by type)
 *   - Bezier-curve connections with arrowheads at node edges
 *   - Pan (space+drag or middle-click) and zoom (scroll wheel, anchored)
 *   - Drag nodes to reposition (debounced save to database)
 *   - Right-click context menu → Connect Forward/Back modal
 *   - Double-click node → Edit Node modal
 *   - Act highlighting (colored halos around nodes belonging to selected act)
 *   - Book switching clears canvas, loads new graph
 *   - Keyboard shortcuts (Delete, Escape, Ctrl+Z undo)
 *
 * Architecture:
 *   - appState: single source of truth (set in main.js)
 *   - renderCanvas(): draws grid, connections, nodes, highlights
 *   - event listeners: mousedown/move/up, dblclick, wheel, contextmenu, keydown
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
    dragOffsetX: 0,
    dragOffsetY: 0,
    panStartX: 0,
    panStartY: 0,
    isPanning: false,
    spaceDown: false,
    validationIssues: [],
    // Undo stack for node operations
    undoStack: [],
    undoIndex: -1,
    // Act highlight (set by toolbar)
    highlightActId: null,
    // Act colors for highlighting
    actColors: [
        "#4a9eff", "#36d399", "#f59e0b", "#f472b6",
        "#8b5cf6", "#ef4444", "#06b6d4", "#84cc16",
    ],
};

// --- API helpers ---

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

// --- Undo support ---

function pushUndo(action) {
    // Discard any future states if we're in the middle of the stack
    appState.undoStack = appState.undoStack.slice(0, appState.undoIndex + 1);
    appState.undoStack.push(action);
    appState.undoIndex = appState.undoStack.length - 1;
    // Limit to 20 steps
    if (appState.undoStack.length > 20) {
        appState.undoStack.shift();
        appState.undoIndex--;
    }
    updateUndoButton();
}

function updateUndoButton() {
    const btn = document.getElementById("btn-undo");
    if (btn) btn.disabled = appState.undoIndex < 0;
}

function undo() {
    if (appState.undoIndex < 0) return;
    const action = appState.undoStack[appState.undoIndex];
    appState.undoIndex--;

    switch (action.type) {
        case "create-node": {
            const idx = appState.nodes.findIndex(n => n.id === action.nodeId);
            if (idx >= 0) {
                appState.nodes.splice(idx, 1);
                appState.choices = appState.choices.filter(
                    c => c.sourceNodeId !== action.nodeId && c.targetId !== action.nodeId
                );
                setStatus(`Undid: created node "${action.title}"`);
            }
            updateUndoButton();
            break;
        }
        case "delete-node": {
            appState.nodes.push(action.node);
            setStatus(`Undid: deleted node "${action.title}"`);
            updateUndoButton();
            break;
        }
        case "move-node": {
            const n = appState.nodes.find(nn => nn.id === action.nodeId);
            if (n) {
                n.x = action.oldX;
                n.y = action.oldY;
                renderCanvas();
                setStatus(`Undid: move node "${action.title}"`);
            }
            updateUndoButton();
            break;
        }
        case "create-choice": {
            const ci = appState.choices.findIndex(c => c.id === action.choiceId);
            if (ci >= 0) {
                appState.choices.splice(ci, 1);
                setStatus(`Undid: created choice`);
            }
            updateUndoButton();
            break;
        }
        default:
            break;
    }
    renderCanvas();
}

// --- Data loading ---

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
    document.getElementById("btn-validate").disabled = false;
    document.getElementById("btn-save").disabled = false;
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
    appState.selectedNodeId = null;
    appState.undoStack = [];
    appState.undoIndex = -1;
    appState.highlightActId = null;
    renderSidebar();
    renderEntityPanel("shared");
    setStatus(`Loaded book: ${data.title} (${appState.nodes.length} nodes, ${appState.choices.length} choices)`);
    document.getElementById("btn-validate").disabled = false;
    document.getElementById("btn-save").disabled = false;
    updateUndoButton();
}

async function createBook(seriesId, title, number) {
    const data = await API.post(`/series/${seriesId}/books`, { title, number });
    await loadBook(data.id);
    setStatus(`Created book: ${title}`);
    return data;
}

// Debounced save for node positions
const _saveTimeouts = new Map();

async function saveNodePosition(nodeId, x, y) {
    const key = `${nodeId}:${Math.round(x)}:${Math.round(y)}`;
    clearTimeout(_saveTimeouts.get(key));
    _saveTimeouts.set(key, setTimeout(() => {
        API.put(`/books/${appState.bookId}/nodes/${nodeId}`, { x, y }).catch(err => {
            setStatus(`Failed to save position: ${err.message}`);
        });
        _saveTimeouts.delete(key);
    }, 300));
}

// --- Node CRUD ---

async function createNode(bookId, opts = {}) {
    const data = await API.post(`/books/${bookId}/nodes`, {
        title: opts.title || "New Node",
        actId: opts.actId || null,
        type: opts.type || "beat",
        x: opts.x || 0,
        y: opts.y || 0,
    });
    appState.nodes.push(data);
    pushUndo({ type: "create-node", nodeId: data.id, title: data.title });
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
    const node = appState.nodes.find(n => n.id === nodeId);
    await API.delete(`/books/${appState.bookId}/nodes/${nodeId}`);
    appState.nodes = appState.nodes.filter(n => n.id !== nodeId);
    appState.choices = appState.choices.filter(c =>
        c.sourceNodeId !== nodeId && c.targetId !== nodeId
    );
    pushUndo({ type: "delete-node", node, title: node?.title });
    renderCanvas();
    setStatus("Node deleted.");
}

async function addChoice(sourceNodeId, targetId, text) {
    const data = await API.post(
        `/books/${appState.bookId}/nodes/${sourceNodeId}/choices`,
        { targetId, text }
    );
    appState.choices.push(data);
    pushUndo({ type: "create-choice", choiceId: data.id });
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

// --- UI Rendering ---

function renderSidebar(seriesList) {
    const container = document.getElementById("sidebar-tree");
    if (!seriesList || seriesList.length === 0) {
        container.innerHTML = '<p class="sidebar-placeholder">No series loaded.</p>';
        return;
    }

    let html = "";
    for (const series of seriesList) {
        const active = series.id === appState.seriesId ? ' class="active"' : "";
        html += `<div class="tree-item${active}">`;
        html += `<span class="tree-label" data-action="select-series" data-series-id="${series.id}">📚 ${series.title}</span>`;
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
                        html += `<span class="tree-label tree-act-label" data-action="select-act" data-act-id="${act.id}">Act ${act.order}: ${act.title}</span>`;
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

/**
 * Draw a rounded rectangle on the canvas context.
 */
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

/**
 * Get the center of a node rect.
 */
function nodeCenter(node) {
    return { x: node.x + 60, y: node.y + 25 };
}

/**
 * Get the edge of a node rect at a given angle (in radians).
 * Uses the rectangle dimensions to find the intersection.
 */
function nodeEdge(node, angle, w, h) {
    const cx = node.x + w / 2;
    const cy = node.y + h / 2;
    const absCos = Math.abs(Math.cos(angle));
    const absSin = Math.abs(Math.sin(angle));
    let t;
    if (w !== 0 && h !== 0) {
        t = Math.min(w / 2 / (absCos || 0.001), h / 2 / (absSin || 0.001));
    } else if (w !== 0) {
        t = w / 2 / (absCos || 0.001);
    } else {
        t = h / 2 / (absSin || 0.001);
    }
    return { x: cx + t * Math.cos(angle), y: cy + t * Math.sin(angle) };
}

/**
 * Draw a bezier curve connection between two nodes with an arrowhead.
 */
function drawConnection(ctx, src, tgt, w, h) {
    const srcCenter = nodeCenter(src);
    const tgtCenter = nodeCenter(tgt);
    const angle = Math.atan2(tgtCenter.y - srcCenter.y, tgtCenter.x - srcCenter.x);

    // Start at the edge of the source node (right side)
    const start = nodeEdge(src, angle, w, h);
    // End at the edge of the target node (left side, opposite direction)
    const end = nodeEdge(tgt, angle + Math.PI, w, h);

    // Bezier control points — pull horizontally for a clean flow
    const dx = Math.abs(end.x - start.x);
    const cpOffset = Math.max(50, dx * 0.4);

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.bezierCurveTo(
        start.x + cpOffset, start.y,
        end.x - cpOffset, end.y,
        end.x, end.y
    );
    ctx.stroke();

    // Arrowhead at the end
    const arrowLen = 10;
    const arrowAngle = 0.4;
    // Tangent at the end of the bezier
    const tangentAngle = Math.atan2(end.y - (3 * (tgtCenter.y) - 2 * start.y), end.x - (3 * (tgtCenter.x) - 2 * (start.x + cpOffset)));

    ctx.beginPath();
    ctx.moveTo(end.x, end.y);
    ctx.lineTo(
        end.x - arrowLen * Math.cos(tangentAngle - arrowAngle),
        end.y - arrowLen * Math.sin(tangentAngle - arrowAngle)
    );
    ctx.moveTo(end.x, end.y);
    ctx.lineTo(
        end.x - arrowLen * Math.cos(tangentAngle + arrowAngle),
        end.y - arrowLen * Math.sin(tangentAngle + arrowAngle)
    );
    ctx.stroke();
}

/**
 * Main canvas render function. Called on every state change.
 */
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

    // Size canvas to container
    const container = canvas.parentElement;
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Apply transform (pan + zoom)
    ctx.save();
    ctx.translate(appState.canvasOffsetX, appState.canvasOffsetY);
    ctx.scale(appState.canvasScale, appState.canvasScale);

    // Background grid
    drawGrid(ctx);

    // Act highlighting
    if (appState.highlightActId) {
        drawActHighlight(ctx);
    }

    // Draw connections (edges)
    ctx.strokeStyle = "#555";
    ctx.lineWidth = 2;
    for (const choice of appState.choices) {
        const src = appState.nodes.find(n => n.id === choice.sourceNodeId);
        const tgt = appState.nodes.find(n => n.id === choice.targetId);
        if (!src || !tgt) continue;
        drawConnection(ctx, src, tgt, 120, 50);
    }

    // Draw nodes
    const NODE_W = 120;
    const NODE_H = 50;
    for (const node of appState.nodes) {
        drawNode(ctx, node, NODE_W, NODE_H);
    }

    ctx.restore();

    // Zoom indicator
    drawZoomIndicator(ctx, canvas);

    // Validation status
    if (appState.validationIssues.length > 0) {
        setStatus(`${appState.validationIssues.length} validation issue(s) — click Validate.`);
    }
}

/**
 * Draw the infinite background grid.
 */
function drawGrid(ctx) {
    const gridSize = 50;
    // Visible area in world coordinates
    const startX = -appState.canvasOffsetX / appState.canvasScale;
    const startY = -appState.canvasOffsetY / appState.canvasScale;
    const endX = (canvas.width - appState.canvasOffsetX) / appState.canvasScale;
    const endY = (canvas.height - appState.canvasOffsetY) / appState.canvasScale;

    ctx.strokeStyle = "#222233";
    ctx.lineWidth = 0.5 / appState.canvasScale;

    // Vertical lines
    for (let x = Math.floor(startX / gridSize) * gridSize; x <= endX; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, startY);
        ctx.lineTo(x, endY);
        ctx.stroke();
    }
    // Horizontal lines
    for (let y = Math.floor(startY / gridSize) * gridSize; y <= endY; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(startX, y);
        ctx.lineTo(endX, y);
        ctx.stroke();
    }
}

/**
 * Draw act-highlight halos around nodes belonging to the selected act.
 */
function drawActHighlight(ctx) {
    const act = appState.acts.find(a => a.id === appState.highlightActId);
    if (!act) return;

    const colorIdx = act.order - 1;
    const haloColor = appState.actColors[colorIdx % appState.actColors.length];

    for (const node of appState.nodes) {
        if (node.actId !== act.id) continue;

        ctx.save();
        ctx.strokeStyle = haloColor;
        ctx.lineWidth = 3 / appState.canvasScale;
        ctx.globalAlpha = 0.6;
        roundRect(ctx, node.x - 3, node.y - 3, 126, 56, 10);
        ctx.stroke();
        ctx.restore();
    }
}

/**
 * Draw a single node as a rounded rectangle with title text.
 */
function drawNode(ctx, node, w, h) {
    const isSelected = node.id === appState.selectedNodeId;

    // Type-based colors
    const typeColors = {
        entry:  { border: "#4caf50", bg: "#1a3a1a" },
        beat:   { border: "#555",    bg: "#1a1a2a" },
        exit:   { border: "#ff9800", bg: "#3a2a0a" },
        ending: { border: "#f44336", bg: "#3a1a1a" },
    };
    const c = typeColors[node.type] || typeColors.beat;

    ctx.save();

    // Selection glow
    if (isSelected) {
        ctx.shadowColor = "#fff";
        ctx.shadowBlur = 12 / appState.canvasScale;
    }

    // Fill and stroke
    ctx.fillStyle = c.bg;
    ctx.strokeStyle = c.border;
    ctx.lineWidth = isSelected ? (3 / appState.canvasScale) : (1.5 / appState.canvasScale);
    roundRect(ctx, node.x, node.y, w, h, 8);
    ctx.fill();
    ctx.stroke();

    ctx.shadowBlur = 0;

    // Node type indicator (small colored dot in top-left)
    ctx.fillStyle = c.border;
    ctx.beginPath();
    ctx.arc(node.x + 8, node.y + 8, 3 / appState.canvasScale, 0, Math.PI * 2);
    ctx.fill();

    // Title text
    ctx.fillStyle = "#fff";
    ctx.font = `${13 / appState.canvasScale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const title = node.title.length > 14 ? node.title.slice(0, 13) + "…" : node.title;
    ctx.fillText(title, node.x + w / 2, node.y + h / 2);

    ctx.restore();
}

/**
 * Draw the zoom percentage indicator in the bottom-right corner.
 */
function drawZoomIndicator(ctx, canvas) {
    ctx.save();
    ctx.fillStyle = "#444";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "bottom";
    ctx.fillText(
        `${Math.round(appState.canvasScale * 100)}%`,
        canvas.width - 10,
        canvas.height - 10
    );
    ctx.restore();
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

// --- Hit testing ---

/**
 * Check if a world-coordinate point falls within a node rectangle.
 */
function hitTestNode(mx, my, node) {
    return mx >= node.x && mx <= node.x + 120 && my >= node.y && my <= node.y + 50;
}

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
        setStatus(`Updated node: ${updates.title}`);
    };

    // Bind delete button
    document.getElementById("modal-edit-delete").onclick = async () => {
        if (confirm(`Delete node "${node.title}"?`)) {
            await deleteNode(node.id);
            closeModal("modal-edit");
        }
    };
}

// --- Canvas context menu (right-click on node) ---

function handleContextMenu(e) {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left - appState.canvasOffsetX) / appState.canvasScale;
    const my = (e.clientY - rect.top - appState.canvasOffsetY) / appState.canvasScale;

    for (const n of appState.nodes) {
        if (hitTestNode(mx, my, n)) {
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
            return;
        }
    }
}

// --- Keyboard shortcuts ---

function handleKeydown(e) {
    // Space bar: start panning
    if (e.code === "Space" && !e.repeat && !appState.spaceDown) {
        e.preventDefault();
        appState.spaceDown = true;
        canvas.style.cursor = "grabbing";
    }

    // Escape: close modals, deselect
    if (e.key === "Escape") {
        document.querySelectorAll(".modal:not(.hidden)").forEach(m => m.classList.add("hidden"));
        appState.selectedNodeId = null;
        renderCanvas();
        return;
    }

    // Delete/Backspace: delete selected node (only when not focused on an input)
    if ((e.key === "Delete" || e.key === "Backspace") &&
        !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
        if (appState.selectedNodeId) {
            const node = appState.nodes.find(n => n.id === appState.selectedNodeId);
            if (node && confirm(`Delete node "${node.title}"?`)) {
                deleteNode(appState.selectedNodeId);
                appState.selectedNodeId = null;
            }
        }
    }

    // Ctrl+Z / Cmd+Z: undo
    if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        e.preventDefault();
        undo();
    }
}

// --- Event delegation (sidebar, modals, toolbar) ---

async function handleClick(e) {
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
    if (action === "select-act") {
        if (appState.highlightActId === actId) {
            appState.highlightActId = null; // toggle off
        } else {
            appState.highlightActId = actId;
        }
        renderCanvas();
        setStatus(`Act highlighting: ${appState.highlightActId ? "ON" : "OFF"}`);
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
}

// --- Initialize ---

document.addEventListener("DOMContentLoaded", () => {
    // Load series list on startup
    loadSeriesList();

    const canvas = document.getElementById("canvas");

    // Canvas mouse handlers
    canvas.addEventListener("mousedown", (e) => {
        // Middle button or space held = pan
        if (e.button === 1 || appState.spaceDown) {
            e.preventDefault();
            appState.isPanning = true;
            appState.panStartX = e.clientX - appState.canvasOffsetX;
            appState.panStartY = e.clientY - appState.canvasOffsetY;
            canvas.style.cursor = "grabbing";
            return;
        }

        if (e.button !== 0) return; // only left click

        const rect = canvas.getBoundingClientRect();
        const mx = (e.clientX - rect.left - appState.canvasOffsetX) / appState.canvasScale;
        const my = (e.clientY - rect.top - appState.canvasOffsetY) / appState.canvasScale;

        // Check if clicking on a node (reverse order: topmost first)
        let clickedNode = null;
        for (let i = appState.nodes.length - 1; i >= 0; i--) {
            if (hitTestNode(mx, my, appState.nodes[i])) {
                clickedNode = appState.nodes[i];
                break;
            }
        }

        if (clickedNode) {
            appState.selectedNodeId = clickedNode.id;
            appState.draggingNode = clickedNode;
            appState.dragOffsetX = mx - clickedNode.x;
            appState.dragOffsetY = my - clickedNode.y;
            renderCanvas();
            return;
        }

        // Click on empty space: deselect
        appState.selectedNodeId = null;
        appState.isPanning = true;
        appState.panStartX = e.clientX - appState.canvasOffsetX;
        appState.panStartY = e.clientY - appState.canvasOffsetY;
        renderCanvas();
    });

    canvas.addEventListener("mousemove", (e) => {
        if (appState.draggingNode) {
            const rect = canvas.getBoundingClientRect();
            const mx = (e.clientX - rect.left - appState.canvasOffsetX) / appState.canvasScale;
            const my = (e.clientY - rect.top - appState.canvasOffsetY) / appState.canvasScale;
            const newX = mx - appState.dragOffsetX;
            const newY = my - appState.dragOffsetY;

            // Record undo before move
            if (!appState._moveRecorded) {
                appState._moveRecorded = true;
                pushUndo({
                    type: "move-node",
                    nodeId: appState.draggingNode.id,
                    title: appState.draggingNode.title,
                    oldX: appState.draggingNode.x,
                    oldY: appState.draggingNode.y,
                });
            }

            appState.draggingNode.x = newX;
            appState.draggingNode.y = newY;
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
            // Debounced save (handled by saveNodePosition)
            saveNodePosition(
                appState.draggingNode.id,
                appState.draggingNode.x,
                appState.draggingNode.y
            );
            appState.draggingNode = null;
            appState._moveRecorded = false;
        }
        appState.isPanning = false;
        canvas.style.cursor = appState.spaceDown ? "grabbing" : "grab";
    });

    canvas.addEventListener("dblclick", (e) => {
        const rect = canvas.getBoundingClientRect();
        const mx = (e.clientX - rect.left - appState.canvasOffsetX) / appState.canvasScale;
        const my = (e.clientY - rect.top - appState.canvasOffsetY) / appState.canvasScale;

        for (let i = appState.nodes.length - 1; i >= 0; i--) {
            if (hitTestNode(mx, my, appState.nodes[i])) {
                openEditModal(appState.nodes[i]);
                return;
            }
        }
    });

    canvas.addEventListener("wheel", (e) => {
        e.preventDefault();
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;

        // Zoom anchored to mouse position
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        const newScale = Math.max(0.2, Math.min(3, appState.canvasScale * delta));

        // Adjust offset so the point under the mouse stays in place
        const wx = (mx - appState.canvasOffsetX) / appState.canvasScale;
        const wy = (my - appState.canvasOffsetY) / appState.canvasScale;
        appState.canvasOffsetX = mx - wx * newScale;
        appState.canvasOffsetY = my - wy * newScale;
        appState.canvasScale = newScale;

        renderCanvas();
    }, { passive: false });

    canvas.addEventListener("contextmenu", handleContextMenu);

    // Global event delegation
    document.addEventListener("click", handleClick);

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
            document.getElementById("modal-connect-text").value = "";
        }
    });

    document.getElementById("modal-connect-back").addEventListener("click", async () => {
        const text = document.getElementById("modal-connect-text").value;
        const targetId = document.getElementById("modal-connect-target").value;
        if (text && targetId && appState.connectSourceId) {
            await addChoice(appState.connectSourceId, targetId, text + " (back)");
            closeModal("modal-connect");
            document.getElementById("modal-connect-text").value = "";
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

    // Keyboard shortcuts
    document.addEventListener("keydown", handleKeydown);

    // Tab switching for entity panel
    document.querySelectorAll(".tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            renderEntityPanel(tab.dataset.tab);
        });
    });

    // Validate button
    document.getElementById("btn-validate").addEventListener("click", async () => {
        if (!appState.bookId) return;
        try {
            // TODO: implement validation endpoint in Phase 3
            setStatus("Validation: no issues found (not yet implemented).");
        } catch (err) {
            setStatus(`Validation error: ${err.message}`);
        }
    });

    // Undo button
    document.getElementById("btn-undo").addEventListener("click", () => {
        undo();
    });
});
