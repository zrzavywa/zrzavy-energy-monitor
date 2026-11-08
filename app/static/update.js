"use strict";

const installedVersion = document.querySelector("#installed-version");
const availableVersion = document.querySelector("#available-version");
const updateStatus = document.querySelector("#update-status");
const checkButton = document.querySelector("#check-update-button");

const releaseCard = document.querySelector("#release-card");
const releaseName = document.querySelector("#release-name");
const publishedAt = document.querySelector("#published-at");
const releaseNotes = document.querySelector("#release-notes");
const releaseLink = document.querySelector("#release-link");

const errorCard = document.querySelector("#update-error");
const errorMessage = document.querySelector("#update-error-message");

const downloadButton = document.querySelector("#download-update-button");
const downloadState = document.querySelector("#download-state");
const downloadProgress = document.querySelector("#download-progress");
const downloadProgressBar = document.querySelector("#download-progress-bar");
const downloadMessage = document.querySelector("#download-message");
const verifiedVersion = document.querySelector("#verified-version");
const installButton = document.querySelector("#install-update-button");
const installationResult = document.querySelector("#installation-result");

const ACTIVE_UPDATE_STATES = new Set([
  "queued",
  "backing_up",
  "preparing",
  "activating",
  "healthchecking",
  "rollback",
]);

async function readJsonResponse(response, fallbackMessage) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("application/json")) {
    throw new Error(
      response.ok ? fallbackMessage : `Serverfehler beim Update: HTTP ${response.status}`,
    );
  }
  try {
    return await response.json();
  } catch (_error) {
    throw new Error("Der Update-Server hat eine ungültige Antwort geliefert.");
  }
}


function formatDate(value) {
  if (!value) {
    return "Nicht angegeben";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

async function loadInstalledVersion() {
  const response = await fetch("/api/system/version", {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Versionsabfrage fehlgeschlagen: HTTP ${response.status}`);
  }

  const payload = await readJsonResponse(response, "Ungültige Versionsantwort.");
  installedVersion.textContent = payload.version;
}

async function checkForUpdate() {
  checkButton.disabled = true;
  updateStatus.textContent = "GitHub wird geprüft …";
  availableVersion.textContent = "–";
  releaseCard.hidden = true;
  errorCard.hidden = true;

  try {
    await loadInstalledVersion();

    const response = await fetch("/api/update/check", {
      headers: {
        Accept: "application/json",
      },
    });

    const payload = await readJsonResponse(response, "Ungültige Updateantwort.");

    if (!response.ok || payload.status !== "ok") {
      throw new Error(
        payload.message || `Updateprüfung fehlgeschlagen: HTTP ${response.status}`,
      );
    }

    installedVersion.textContent = payload.installed_version;
    availableVersion.textContent = payload.available_version;

    if (payload.update_available) {
      updateStatus.textContent = "Neue Version verfügbar";
    } else {
      updateStatus.textContent = "Zrzavy Energy Monitor ist aktuell";
    }
    
    downloadButton.disabled = !payload.update_available;
    
    releaseName.textContent =
      payload.release_name || `Zrzavy Energy Monitor ${payload.available_version}`;

    publishedAt.textContent = formatDate(payload.published_at);
    releaseNotes.textContent =
      payload.release_notes || "Für dieses Release sind keine Hinweise vorhanden.";

    if (payload.release_url) {
      releaseLink.href = payload.release_url;
      releaseLink.hidden = false;
    } else {
      releaseLink.hidden = true;
    }

    releaseCard.hidden = false;
  } catch (error) {
    updateStatus.textContent = "Fehler";
    errorMessage.textContent = error.message;
    errorCard.hidden = false;
  } finally {
    checkButton.disabled = false;
  }
}

function sleep(milliseconds) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

async function fetchUpdateStatus() {
  const response = await fetch("/api/update/status", {
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      `Statusabfrage fehlgeschlagen: HTTP ${response.status}`,
    );
  }

  return readJsonResponse(response, "Ungültige Statusantwort.");
}


async function pollInstallationStatus() {
  for (let attempt = 0; attempt < 180; attempt += 1) {
    try {
      const payload = await fetchUpdateStatus();
      renderDownloadStatus(payload);

      if (payload.state === "success") {
        checkButton.disabled = false;
        return;
      }

      if (payload.state === "failed") {
        checkButton.disabled = false;
        downloadButton.disabled = false;
        return;
      }
    } catch (error) {
      renderDownloadStatus({
        state: "activating",
        progress: 85,
        message:
          "Zrzavy Energy Monitor wird neu gestartet. Verbindung wird wiederhergestellt …",
      });
    }

    await sleep(2000);
  }

  throw new Error(
    "Die Updateinstallation hat das maximale Zeitlimit überschritten.",
  );
}

async function installUpdate() {
  installButton.disabled = true;
  downloadButton.disabled = true;
  checkButton.disabled = true;
  errorCard.hidden = true;

  try {
    const response = await fetch("/api/update/install", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });

    const payload = await readJsonResponse(response, "Ungültige Installationsantwort.");

    if (!response.ok) {
      throw new Error(
        payload.message ||
          `Installation konnte nicht gestartet werden: HTTP ${response.status}`,
      );
    }

    await pollInstallationStatus();
  } catch (error) {
    errorMessage.textContent = error.message;
    errorCard.hidden = false;

    checkButton.disabled = false;
  }
}


function formatUpdateState(state) {
  const labels = {
    idle: "Bereit",
    checking: "GitHub wird geprüft",
    downloading: "Download läuft",
    verified: "Paket geprüft",
    queued: "Installation vorgemerkt",
    backing_up: "Backup wird erstellt",
    preparing: "Neue Version wird vorbereitet",
    activating: "Neue Version wird aktiviert",
    healthchecking: "Funktionstest läuft",
    rollback: "Rollback läuft",
    success: "Update erfolgreich",
    failed: "Update fehlgeschlagen",
  };

  return labels[state] || state || "Unbekannt";
}


function formatStatusTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString("de-DE", {dateStyle: "medium", timeStyle: "short"});
}

// A stored status that names another version than the running one does not
// describe the current installation: it stays behind whenever a release is
// installed by hand. The API marks such a record with status_is_historic, so
// the panel shows it as history instead of claiming a fresh success.
function buildDownloadStatusView(payload) {
  const state = payload.state || "idle";
  const progress = Number(payload.progress || 0);
  const storedVersion = payload.available_version || "";
  const runningVersion = payload.installed_version || "";

  if (!payload.status_is_historic) {
    return {
      stateLabel: formatUpdateState(state),
      progressLabel: `${progress} %`,
      progressValue: progress,
      verifiedVersion: storedVersion || "–",
      message: payload.message || "Kein Status verfügbar.",
      result:
        state === "success"
          ? `Zrzavy Energy Monitor ${storedVersion} wurde erfolgreich installiert.`
          : state === "failed"
            ? payload.message || "Die Installation ist fehlgeschlagen."
            : null,
      historic: false
    };
  }

  const when = formatStatusTime(payload.updated_at);
  const target = storedVersion ? `Version ${storedVersion}` : "eine frühere Version";
  const outcome =
    state === "failed"
      ? ` Der Vorgang endete mit: ${payload.message || "Fehler"}.`
      : "";
  return {
    stateLabel: `${formatUpdateState(state)} · älterer Vorgang`,
    progressLabel: "–",
    progressValue: 0,
    verifiedVersion: "–",
    message: `${when ? `Am ${when}` : "Zuletzt"} wurde ${target} über den Updater eingespielt.${outcome} Die laufende Version ${runningVersion || "–"} stammt nicht aus diesem Vorgang.`,
    result: null,
    historic: true
  };
}

function renderDownloadStatus(payload) {
  const view = buildDownloadStatusView(payload);

  downloadState.textContent = view.stateLabel;
  downloadProgress.textContent = view.progressLabel;
  downloadProgressBar.value = view.progressValue;
  downloadMessage.textContent = view.message;
  verifiedVersion.textContent = view.verifiedVersion;

  const canInstall =
    (payload.state || "idle") === "verified" &&
    Boolean(payload.available_version) &&
    Boolean(payload.archive_path) &&
    !view.historic;

  if (installButton) {
    installButton.disabled = !canInstall;
  }

  if (view.result) {
    installationResult.hidden = false;
    installationResult.textContent = view.result;
  } else {
    installationResult.hidden = true;
  }
}

async function loadDownloadStatus() {
  const response = await fetch("/api/update/status", {
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Statusabfrage fehlgeschlagen: HTTP ${response.status}`);
  }

  const payload = await readJsonResponse(response, "Ungültige Statusantwort.");
  renderDownloadStatus(payload);

  return payload;
}

async function downloadUpdate() {
  downloadButton.disabled = true;
  errorCard.hidden = true;

  renderDownloadStatus({
    state: "starting",
    progress: 5,
    message: "Update-Download wird gestartet.",
  });

  try {
    const response = await fetch("/api/update/download", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    });

    const payload = await readJsonResponse(response, "Ungültige Downloadantwort.");
    renderDownloadStatus(payload);

    if (!response.ok) {
      throw new Error(
        payload.message ||
          `Download fehlgeschlagen: HTTP ${response.status}`,
      );
    }
  } catch (error) {
    renderDownloadStatus({
      state: "failed",
      progress: 0,
      message: error.message,
    });
    errorMessage.textContent = error.message;
    errorCard.hidden = false;
  } finally {
    downloadButton.disabled = false;
  }
}

checkButton.addEventListener("click", checkForUpdate);
downloadButton.addEventListener("click", downloadUpdate);

if (installButton) {
  installButton.addEventListener("click", installUpdate);
}


loadDownloadStatus()
  .then((payload) => {
    if (ACTIVE_UPDATE_STATES.has(payload?.state)) {
      return pollInstallationStatus();
    }

    return null;
  })
  .catch((error) => {
    console.error(error);
  });

checkForUpdate();
