/* Zrzavy Energy Monitor - device availability timeline (/acquisition). */
"use strict";

const AVAILABILITY_ENDPOINT = "/api/devices/availability";
const AVAILABILITY_COLORS = {
  good: "#15845b",
  limited: "#d9a11c",
  bad: "#b34141",
  inactive: "#b9c0bc",
  nodata: "#e2e6e3",
};
const AVAILABILITY_STATE_LABELS = {
  good: "erreichbar",
  limited: "erreichbar mit Einschränkung",
  bad: "nicht erreichbar",
  inactive: "inaktiv",
  nodata: "keine Daten",
};

const availabilityRows = document.getElementById("availability-rows");
const availabilityTitle = document.getElementById("availability-title");
const periodButtons = Array.from(document.querySelectorAll(".availability-period"));

let availabilityPeriod = "day";
let availabilityPayload = null;
let availabilityRequest = 0;
let availabilityTooltip = null;

function availabilityFormatPercent(value) {
  return typeof value === "number" ? `${value.toFixed(1).replace(".", ",")} %` : "–";
}

async function loadAvailability(period = availabilityPeriod) {
  if (!availabilityRows) return;
  availabilityPeriod = period;
  const ticket = ++availabilityRequest;
  try {
    const response = await fetch(`${AVAILABILITY_ENDPOINT}?period=${encodeURIComponent(period)}`);
    if (!response.ok) throw new Error("Verfügbarkeit konnte nicht geladen werden");
    const payload = await response.json();
    if (ticket !== availabilityRequest) return;
    availabilityPayload = payload;
    renderAvailability();
  } catch (error) {
    if (ticket !== availabilityRequest) return;
    availabilityRows.textContent = error.message;
  }
}

function renderAvailability() {
  const payload = availabilityPayload;
  if (!payload) return;
  if (availabilityTitle) {
    availabilityTitle.textContent = `${payload.title} · ${payload.timezone} · Auflösung 1 Stunde`;
  }
  availabilityRows.textContent = "";
  const visible = payload.devices.filter((device) => device.configured);
  const hidden = payload.devices.filter((device) => !device.configured);
  if (!visible.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "Keine Messstelle ist aktiviert. Bitte zuerst die Konfiguration prüfen.";
    availabilityRows.appendChild(empty);
    return;
  }
  for (const device of visible) {
    availabilityRows.appendChild(buildAvailabilityRow(device, payload));
  }
  if (hidden.length) {
    const note = document.createElement("p");
    note.className = "hint availability-inactive";
    note.textContent =
      "Nicht dargestellt, weil nicht konfiguriert: " +
      hidden.map((device) => device.name).join(", ") +
      ".";
    availabilityRows.appendChild(note);
  }
}

function buildAvailabilityRow(device, payload) {
  const row = document.createElement("div");
  row.className = "availability-row";

  const head = document.createElement("div");
  head.className = "availability-row-head";

  const name = document.createElement("strong");
  name.textContent = device.name;
  head.appendChild(name);

  const state = document.createElement("span");
  state.className = `availability-state state-${device.state}`;
  state.textContent = AVAILABILITY_STATE_LABELS[device.state] || device.state;
  head.appendChild(state);

  const summary = document.createElement("span");
  summary.className = "availability-summary";
  summary.textContent = describeAvailability(device, payload);
  head.appendChild(summary);
  row.appendChild(head);

  const canvas = document.createElement("canvas");
  canvas.__availabilityDevice = device;
  canvas.className = "availability-canvas";
  canvas.setAttribute("role", "img");
  canvas.setAttribute(
    "aria-label",
    `Verfügbarkeit ${device.name}: ${summary.textContent}`,
  );
  row.appendChild(canvas);
  drawAvailabilityBars(canvas);
  attachAvailabilityTooltip(canvas, device, payload);
  return row;
}

function describeAvailability(device, payload) {
  const summary = device.summary || {};
  if (!summary.observations) {
    return payload.period === "day"
      ? "keine Messung an diesem Tag"
      : "keine Messung in diesem Zeitraum";
  }
  const parts = [`${availabilityFormatPercent(summary.reachable_pct)} erreichbar`];
  if (summary.unreachable_pct) {
    parts.push(`${availabilityFormatPercent(summary.unreachable_pct)} nicht erreichbar`);
  }
  if (summary.degraded_pct) {
    parts.push(`davon ${availabilityFormatPercent(summary.degraded_pct)} mit Einschränkung`);
  }
  const gaps = summary.hours_in_period - summary.hours_observed;
  if (gaps > 0) {
    parts.push(`${gaps} h ohne Daten`);
  }
  if (device.coverage === "derived") {
    parts.push("abgeleitet aus Messwerten");
  }
  return parts.join(" · ");
}

function availabilityBarSegments(bucket) {
  const [online, degraded, offline, disabled] = bucket;
  const observed = online + degraded + offline + disabled;
  return { online, degraded, offline, disabled, observed };
}

function drawAvailabilityBars(canvas) {
  const cssWidth = Math.max(320, canvas.parentElement.clientWidth - 2);
  const cssHeight = 26;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(cssWidth * ratio);
  canvas.height = Math.round(cssHeight * ratio);
  canvas.style.width = `${cssWidth}px`;
  canvas.style.height = `${cssHeight}px`;
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, cssWidth, cssHeight);

  const payload = availabilityPayload;
  const device = canvas.__availabilityDevice;
  const buckets = (device && device.buckets) || [];
  if (!buckets.length) return;
  const slot = cssWidth / buckets.length;
  const barWidth = Math.max(1, Math.floor(slot) - (slot > 4 ? 1 : 0));

  buckets.forEach((bucket, index) => {
    const segment = availabilityBarSegments(bucket);
    const x = index * slot;
    if (!segment.observed) {
      context.fillStyle = AVAILABILITY_COLORS.nodata;
      context.fillRect(x, 6, Math.max(1, barWidth), cssHeight - 12);
      return;
    }
    let offset = 0;
    for (const [key, value] of [
      ["good", segment.online],
      ["limited", segment.degraded],
      ["bad", segment.offline],
      ["inactive", segment.disabled],
    ]) {
      if (!value) continue;
      const height = ((cssHeight - 8) * value) / segment.observed;
      context.fillStyle = AVAILABILITY_COLORS[key];
      context.fillRect(x, 4 + offset, Math.max(1, barWidth), height);
      offset += height;
    }
  });
}

function attachAvailabilityTooltip(canvas, device, payload) {
  canvas.addEventListener("pointermove", (event) => {
    const rect = canvas.getBoundingClientRect();
    const index = Math.floor(
      ((event.clientX - rect.left) / rect.width) * (device.buckets || []).length,
    );
    const bucket = (device.buckets || [])[index];
    if (!bucket) {
      hideAvailabilityTooltip();
      return;
    }
    showAvailabilityTooltip(event, describeBucket(bucket, payload, index));
  });
  canvas.addEventListener("pointerleave", hideAvailabilityTooltip);
}

function describeBucket(bucket, payload, index) {
  const start = new Date((payload.period_start_epoch + index * payload.bucket_seconds) * 1000);
  const end = new Date(start.getTime() + payload.bucket_seconds * 1000);
  const time = `${start.toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"})}–${end.toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"})}`;
  const date = start.toLocaleDateString("de-DE", {day: "2-digit", month: "2-digit"});
  const segment = availabilityBarSegments(bucket);
  if (!segment.observed) {
    return `${date} ${time}: keine Daten`;
  }
  const parts = [];
  if (segment.online) parts.push(`${segment.online}× erreichbar`);
  if (segment.degraded) parts.push(`${segment.degraded}× mit Einschränkung`);
  if (segment.offline) parts.push(`${segment.offline}× nicht erreichbar`);
  return `${date} ${time}: ${parts.join(", ")}`;
}

function showAvailabilityTooltip(event, text) {
  if (!availabilityTooltip) {
    availabilityTooltip = document.createElement("div");
    availabilityTooltip.className = "availability-tooltip";
    document.body.appendChild(availabilityTooltip);
  }
  availabilityTooltip.textContent = text;
  availabilityTooltip.style.left = `${event.clientX + 12}px`;
  availabilityTooltip.style.top = `${event.clientY - 28}px`;
  availabilityTooltip.classList.add("visible");
}

function hideAvailabilityTooltip() {
  if (availabilityTooltip) availabilityTooltip.classList.remove("visible");
}

for (const button of periodButtons) {
  button.addEventListener("click", () => {
    for (const other of periodButtons) {
      const active = other === button;
      other.classList.toggle("is-active", active);
      other.setAttribute("aria-pressed", active ? "true" : "false");
    }
    loadAvailability(button.dataset.period || "day");
  });
}

let availabilityResizeTimer = null;
window.addEventListener("resize", () => {
  if (!availabilityPayload) return;
  window.clearTimeout(availabilityResizeTimer);
  availabilityResizeTimer = window.setTimeout(() => {
    for (const canvas of document.querySelectorAll(".availability-canvas")) {
      drawAvailabilityBars(canvas);
    }
  }, 120);
});

loadAvailability("day");
