document.addEventListener("DOMContentLoaded", () => {
    init().catch((err) => {
        setError(`Failed to initialize dashboard: ${err.message}`);
    });
});

let agreements = [];
let filtered = [];
let page = 1;
const PAGE_SIZE = 25;
let sortCriteria = [{ key: "confidence", dir: "desc" }];
const TOP_CATEGORY_LIMIT = 30;
let allCategories = [];
let topCategories = [];
let topCategorySet = new Set();
let categoryDisplayMap = new Map();

const NUMERIC_SORT_KEYS = new Set(["royalty_rate", "upfront_amount", "filing_year", "confidence"]);

let categoryChart;
let financialChart;

async function init() {
    const payload = await fetchSummary();
    const summary = payload.summary || {};
    agreements = payload.all_agreements || payload.agreements || [];
    filtered = [...agreements];

    renderMeta(summary);
    renderKpis(payload, agreements);
    hydrateFilters(agreements);
    wireFilters();
    wireSortHeaders();
    applyFilters();
}

async function fetchSummary() {
    const res = await fetch("../license_summary.json");
    if (!res.ok) {
        throw new Error(`HTTP ${res.status} loading ../license_summary.json`);
    }
    return res.json();
}

function renderMeta(summary) {
    const stamp = summary.scan_timestamp || "unknown";
    const files = numberFmt(summary.total_license_files || 0);
    const errors = numberFmt(summary.scan_errors || 0);
    document.getElementById("scan-meta").textContent = `Scan: ${stamp} | Files: ${files} | Errors: ${errors}`;
}

function renderKpis(payload, rows) {
    const summary = payload.summary || {};
    const both = payload?.financial_completeness?.both || 0;
    document.getElementById("kpi-agreements-overall").textContent = numberFmt(summary.total_agreements || rows.length);
    document.getElementById("kpi-companies-overall").textContent = numberFmt(summary.companies_with_licenses || uniqueCount(rows.map((r) => r.cik)));
    document.getElementById("kpi-both-overall").textContent = numberFmt(both);
    document.getElementById("kpi-avg-royalty-overall").textContent = avgRoyalty(rows);

    renderFilteredKpis(rows);
}

function hydrateFilters(rows) {
    const yearSel = document.getElementById("filing-year");

    buildCategoryLists(rows);
    renderCategoryOptions(false);
    fillSelect(yearSel, uniqueSorted(rows.map((r) => String(r.filing_year || ""))).filter((y) => y));
}

function buildCategoryLists(rows) {
    const counter = new Map();
    categoryDisplayMap = new Map();
    rows.forEach((r) => {
        const raw = normalizeCategoryLabel(r.tech_category);
        if (!raw) return;
        const key = normalizeCategoryKey(raw);
        if (!key) return;
        if (!categoryDisplayMap.has(key)) categoryDisplayMap.set(key, raw);
        counter.set(key, (counter.get(key) || 0) + 1);
    });

    allCategories = [...counter.keys()].sort((a, b) => (categoryDisplayMap.get(a) || a).localeCompare(categoryDisplayMap.get(b) || b));
    topCategories = [...counter.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, TOP_CATEGORY_LIMIT)
        .map((x) => x[0]);
    topCategorySet = new Set(topCategories);
}

function renderCategoryOptions(showAll) {
    const categorySel = document.getElementById("category");
    const prev = categorySel.value;

    categorySel.innerHTML = "";
    const allOpt = document.createElement("option");
    allOpt.value = "";
    allOpt.textContent = "All";
    categorySel.appendChild(allOpt);

    if (!showAll && allCategories.length > topCategories.length) {
        const othersOpt = document.createElement("option");
        othersOpt.value = "__others__";
        othersOpt.textContent = `Other (outside top ${TOP_CATEGORY_LIMIT})`;
        categorySel.appendChild(othersOpt);
    }

    const source = showAll ? allCategories : topCategories;
    appendCategoryOptions(categorySel, source);

    if ([...categorySel.options].some((o) => o.value === prev)) {
        categorySel.value = prev;
    }

    const note = document.getElementById("category-mode-note");
    if (note) {
        note.textContent = showAll
            ? `Showing all categories (${allCategories.length})`
            : `Showing top ${Math.min(TOP_CATEGORY_LIMIT, topCategories.length)} of ${allCategories.length} categories`;
    }
}

function wireFilters() {
    ["search", "category", "filing-year", "confidence"].forEach((id) => {
        document.getElementById(id).addEventListener("input", applyFilters);
        document.getElementById(id).addEventListener("change", applyFilters);
    });

    document.getElementById("show-all-categories").addEventListener("change", (evt) => {
        renderCategoryOptions(evt.target.checked);
        applyFilters();
    });

    [
        "exclude-missing-licensor",
        "exclude-missing-licensee",
        "exclude-missing-royalty",
        "exclude-missing-upfront",
        "exclude-missing-confidence"
    ].forEach((id) => {
        document.getElementById(id).addEventListener("change", applyFilters);
    });

    document.getElementById("prev").addEventListener("click", () => {
        if (page > 1) {
            page -= 1;
            renderTable();
        }
    });

    document.getElementById("next").addEventListener("click", () => {
        const maxPage = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
        if (page < maxPage) {
            page += 1;
            renderTable();
        }
    });

    document.getElementById("reset-filters").addEventListener("click", () => {
        document.getElementById("search").value = "";
        document.getElementById("category").value = "";
        document.getElementById("filing-year").value = "";
        document.getElementById("confidence").value = "";
        document.getElementById("show-all-categories").checked = false;
        renderCategoryOptions(false);
        document.getElementById("exclude-missing-licensor").checked = false;
        document.getElementById("exclude-missing-licensee").checked = false;
        document.getElementById("exclude-missing-royalty").checked = false;
        document.getElementById("exclude-missing-upfront").checked = false;
        document.getElementById("exclude-missing-confidence").checked = false;
        sortCriteria = [{ key: "confidence", dir: "desc" }];
        applyFilters();
    });
}

function wireSortHeaders() {
    document.querySelectorAll("th.sortable").forEach((header) => {
        header.addEventListener("click", (evt) => {
            const key = header.dataset.sort;
            if (!key) return;

            if (evt.shiftKey) {
                upsertSecondarySort(key);
            } else {
                setPrimarySort(key);
            }

            applySort();
            updateSortIndicators();
            page = 1;
            renderTable();
        });
    });
}

function applyFilters() {
    const q = document.getElementById("search").value.trim().toLowerCase();
    const category = document.getElementById("category").value;
    const year = document.getElementById("filing-year").value;
    const minConfidence = document.getElementById("confidence").value;
    const excludeMissingLicensor = document.getElementById("exclude-missing-licensor").checked;
    const excludeMissingLicensee = document.getElementById("exclude-missing-licensee").checked;
    const excludeMissingRoyalty = document.getElementById("exclude-missing-royalty").checked;
    const excludeMissingUpfront = document.getElementById("exclude-missing-upfront").checked;
    const excludeMissingConfidence = document.getElementById("exclude-missing-confidence").checked;

    filtered = agreements.filter((r) => {
        const textHit = !q || [r.company, r.licensor_name, r.licensee_name, r.tech_name, r.tech_category]
            .filter(Boolean)
            .some((v) => String(v).toLowerCase().includes(q));

        const normalizedCategory = normalizeCategoryKey(r.tech_category);
        const categoryHit = !category
            || (category === "__others__" ? !topCategorySet.has(normalizedCategory) : normalizedCategory === category);
        const yearHit = !year || String(r.filing_year || "") === year;

        let confidenceHit = true;
        if (minConfidence) {
            const c = Number(r.confidence);
            confidenceHit = !Number.isNaN(c) && c >= Number(minConfidence);
        }

        const licensorHit = !excludeMissingLicensor || hasPresentText(r.licensor_name);
        const licenseeHit = !excludeMissingLicensee || hasPresentText(r.licensee_name);
        const royaltyHit = !excludeMissingRoyalty || hasPresentNumber(r.royalty_rate);
        const upfrontHit = !excludeMissingUpfront || hasPresentNumber(r.upfront_amount);
        const confidenceValueHit = !excludeMissingConfidence || hasPresentNumber(r.confidence);

        return (
            textHit &&
            categoryHit &&
            yearHit &&
            confidenceHit &&
            licensorHit &&
            licenseeHit &&
            royaltyHit &&
            upfrontHit &&
            confidenceValueHit
        );
    });

    applySort();
    updateSortIndicators();
    page = 1;
    renderFilteredKpis(filtered);
    renderAll();
}

function applySort() {
    filtered.sort((a, b) => {
        for (const criterion of sortCriteria) {
            const cmp = compareByKey(a, b, criterion.key, criterion.dir);
            if (cmp !== 0) return cmp;
        }
        return 0;
    });
}

function updateSortIndicators() {
    document.querySelectorAll(".sort-ind").forEach((span) => {
        span.textContent = "";
    });

    sortCriteria.forEach((criterion, idx) => {
        const target = document.getElementById(`sort-${criterion.key}`);
        if (!target) return;
        const glyph = criterion.dir === "asc" ? "^" : "v";
        target.textContent = `${glyph}${idx + 1}`;
    });
}

function renderAll() {
    renderCharts();
    renderTable();
}

function renderCharts() {
    const categoryTop = topCounts(filtered.map((r) => r.tech_category || "Unknown"), 8);
    const financial = {
        both: 0,
        upfrontOnly: 0,
        royaltyOnly: 0,
        neither: 0
    };

    filtered.forEach((r) => {
        if (r.has_upfront && r.has_royalty) financial.both += 1;
        else if (r.has_upfront) financial.upfrontOnly += 1;
        else if (r.has_royalty) financial.royaltyOnly += 1;
        else financial.neither += 1;
    });

    if (categoryChart) categoryChart.destroy();
    if (financialChart) financialChart.destroy();

    categoryChart = new Chart(document.getElementById("category-chart"), {
        type: "bar",
        data: {
            labels: categoryTop.labels,
            datasets: [{
                label: "Agreements",
                data: categoryTop.values,
                backgroundColor: "#006d77"
            }]
        },
        options: {
            plugins: { legend: { display: false }, title: { display: true, text: "Top Technology Categories" } },
            scales: { x: { ticks: { maxRotation: 0 } } }
        }
    });

    financialChart = new Chart(document.getElementById("financial-chart"), {
        type: "doughnut",
        data: {
            labels: ["Both", "Upfront Only", "Royalty Only", "Neither"],
            datasets: [{
                data: [financial.both, financial.upfrontOnly, financial.royaltyOnly, financial.neither],
                backgroundColor: ["#006d77", "#83c5be", "#ffb703", "#adb5bd"]
            }]
        },
        options: {
            plugins: { legend: { position: "bottom" }, title: { display: true, text: "Financial Term Completeness" } }
        }
    });
}

function renderTable() {
    const tbody = document.getElementById("rows");
    tbody.innerHTML = "";

    const start = (page - 1) * PAGE_SIZE;
    const end = start + PAGE_SIZE;
    const pageRows = filtered.slice(start, end);

    pageRows.forEach((r) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${safe(r.company)}</td>
            <td>${safe(r.ticker)}</td>
            <td>${safe(r.licensor_name)}</td>
            <td>${safe(r.licensee_name)}</td>
            <td>${safe(r.tech_category)}</td>
            <td>${formatPercent(r.royalty_rate)}</td>
            <td>${formatMoney(r.upfront_amount, r.upfront_currency)}</td>
            <td>${safe(r.filing_year)}</td>
            <td>${formatConfidence(r.confidence)}</td>
        `;
        tbody.appendChild(tr);
    });

    const maxPage = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    document.getElementById("page").textContent = `Page ${page} / ${maxPage} | Rows: ${numberFmt(filtered.length)}`;
    document.getElementById("prev").disabled = page <= 1;
    document.getElementById("next").disabled = page >= maxPage;
}

function fillSelect(select, values) {
    values.forEach((v) => {
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = v;
        select.appendChild(opt);
    });
}

function appendCategoryOptions(select, keys) {
    keys.forEach((key) => {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = categoryDisplayMap.get(key) || key;
        select.appendChild(opt);
    });
}

function topCounts(values, n) {
    const counts = new Map();
    values.forEach((v) => counts.set(v, (counts.get(v) || 0) + 1));
    const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, n);
    return {
        labels: sorted.map((x) => x[0]),
        values: sorted.map((x) => x[1])
    };
}

function uniqueSorted(values) {
    return [...new Set(values.filter(Boolean).map((v) => String(v)))].sort((a, b) => a.localeCompare(b));
}

function normalizeCategoryLabel(v) {
    if (v === null || v === undefined) return "";
    const s = String(v).trim();
    if (!s) return "";
    return s;
}

function normalizeCategoryKey(v) {
    const s = normalizeCategoryLabel(v);
    if (!s) return "";
    return s.toLowerCase();
}

function uniqueCount(values) {
    return new Set(values.filter(Boolean)).size;
}

function avgRoyalty(rows) {
    const list = rows
        .map((r) => Number(r.royalty_rate))
        .filter((v) => !Number.isNaN(v) && v > 0 && v < 100);
    if (!list.length) return "N/A";
    return `${(list.reduce((a, b) => a + b, 0) / list.length).toFixed(2)}%`;
}

function formatPercent(v) {
    if (v === null || v === undefined || String(v).trim() === "") return "-";
    const n = Number(v);
    if (Number.isNaN(n)) return "-";
    return `${n.toFixed(2)}%`;
}

function formatMoney(v, ccy) {
    if (v === null || v === undefined || String(v).trim() === "") return "-";
    const n = Number(v);
    if (Number.isNaN(n)) return "-";
    const prefix = ccy ? `${ccy} ` : "$";
    return `${prefix}${n.toLocaleString()}`;
}

function formatConfidence(v) {
    if (v === null || v === undefined || String(v).trim() === "") return "-";
    const n = Number(v);
    if (Number.isNaN(n)) return "-";
    return n.toFixed(2);
}

function numberFmt(v) {
    const n = Number(v);
    if (Number.isNaN(n)) return "0";
    return n.toLocaleString();
}

function safe(v) {
    return v === null || v === undefined || v === "" ? "-" : String(v);
}

function setError(message) {
    document.getElementById("error-msg").textContent = message;
}

function renderFilteredKpis(rows) {
    const both = rows.filter((r) => r.has_upfront && r.has_royalty).length;
    document.getElementById("kpi-agreements-filtered").textContent = numberFmt(rows.length);
    document.getElementById("kpi-companies-filtered").textContent = numberFmt(uniqueCount(rows.map((r) => r.cik)));
    document.getElementById("kpi-both-filtered").textContent = numberFmt(both);
    document.getElementById("kpi-avg-royalty-filtered").textContent = avgRoyalty(rows);
}

function hasPresentText(v) {
    if (v === null || v === undefined) return false;
    const s = String(v).trim().toLowerCase();
    return s !== "" && s !== "-" && s !== "unknown" && s !== "n/a" && s !== "none";
}

function hasPresentNumber(v) {
    if (v === null || v === undefined || String(v).trim() === "") return false;
    const n = Number(v);
    return !Number.isNaN(n);
}

function getComparableValue(row, key) {
    const raw = row[key];
    if (NUMERIC_SORT_KEYS.has(key)) {
        if (!hasPresentNumber(raw)) return null;
        return Number(raw);
    }
    if (!hasPresentText(raw)) return null;
    return String(raw).trim().toLowerCase();
}

function isMissingComparable(v) {
    return v === null || v === undefined || v === "";
}

function defaultSortDir(key) {
    return NUMERIC_SORT_KEYS.has(key) ? "desc" : "asc";
}

function setPrimarySort(key) {
    if (sortCriteria.length === 1 && sortCriteria[0].key === key) {
        sortCriteria[0].dir = sortCriteria[0].dir === "asc" ? "desc" : "asc";
        return;
    }

    const existing = sortCriteria.find((c) => c.key === key);
    const dir = existing ? existing.dir : defaultSortDir(key);
    sortCriteria = [{ key, dir }];
}

function upsertSecondarySort(key) {
    const idx = sortCriteria.findIndex((c) => c.key === key);
    if (idx === -1) {
        sortCriteria.push({ key, dir: defaultSortDir(key) });
        return;
    }
    sortCriteria[idx].dir = sortCriteria[idx].dir === "asc" ? "desc" : "asc";
}

function compareByKey(a, b, key, dir) {
    const av = getComparableValue(a, key);
    const bv = getComparableValue(b, key);
    const dirMul = dir === "asc" ? 1 : -1;

    const aMissing = isMissingComparable(av);
    const bMissing = isMissingComparable(bv);
    if (aMissing && bMissing) return 0;
    if (aMissing) return 1;
    if (bMissing) return -1;

    if (typeof av === "number" && typeof bv === "number") {
        return (av - bv) * dirMul;
    }

    return String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: "base" }) * dirMul;
}
