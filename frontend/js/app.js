// AeroSOP App JavaScript

const API_BASE = "";

// State
const state = {
  currentLocation: "London",
  currentActivity: "cycling",
  vulnerableGroups: [],
  activeTab: "tab-advisor",
  sopsList: [],
  lastAdvisoryText: "",
  isListening: false,
};

// DOM Elements
const elements = {
  tabs: document.querySelectorAll(".nav-tab"),
  tabViews: document.querySelectorAll(".tab-view"),
  cityInput: document.getElementById("global-city-input"),
  btnSearchCity: document.getElementById("btn-search-city"),
  btnGeoDetect: document.getElementById("btn-geo-detect"),
  activityChips: document.querySelectorAll(".chip-item"),
  demoCheckboxes: document.querySelectorAll(".demo-checkbox"),
  
  // Weather Display Elements
  currentLocationText: document.getElementById("current-location-text"),
  liveClock: document.getElementById("live-clock"),
  currentTemp: document.getElementById("current-temp"),
  apparentTemp: document.getElementById("apparent-temp"),
  weatherDesc: document.getElementById("weather-description"),
  weatherIcon: document.getElementById("weather-main-icon"),
  tempMin: document.getElementById("temp-min"),
  tempMax: document.getElementById("temp-max"),
  metricWind: document.getElementById("metric-wind"),
  metricGusts: document.getElementById("metric-gusts"),
  metricPrecip: document.getElementById("metric-precip"),
  metricPrecipProb: document.getElementById("metric-precip-prob"),
  metricUv: document.getElementById("metric-uv"),
  metricVis: document.getElementById("metric-vis"),
  metricHumidity: document.getElementById("metric-humidity"),
  metricLightning: document.getElementById("metric-lightning"),
  gaugeFill: document.getElementById("gauge-fill"),
  safetyScoreValue: document.getElementById("safety-score-value"),
  safetyStatusBadge: document.getElementById("safety-status-badge"),
  safetyStatusText: document.getElementById("safety-status-text"),
  hourlyForecastList: document.getElementById("hourly-forecast-list"),
  dailyForecastList: document.getElementById("daily-forecast-list"),
  gearItemsList: document.getElementById("gear-items-list"),
  
  // SOP Alert Box
  sopAlertBadge: document.getElementById("sop-alert-badge"),
  sopAlertBody: document.getElementById("sop-alert-body"),
  
  // Chat Elements
  chatMessages: document.getElementById("chat-messages"),
  advisorForm: document.getElementById("advisor-form"),
  chatUserInput: document.getElementById("chat-user-input"),
  btnMic: document.getElementById("btn-mic"),
  btnSpeak: document.getElementById("btn-speak-advisory"),
  btnClearChat: document.getElementById("btn-clear-chat"),
  suggestButtons: document.querySelectorAll(".suggest-btn"),
  
  // Simulator Elements
  simActivitySelect: document.getElementById("sim-activity-select"),
  simTemp: document.getElementById("sim-temp"),
  simWind: document.getElementById("sim-wind"),
  simGusts: document.getElementById("sim-gusts"),
  simPrecip: document.getElementById("sim-precip"),
  simUv: document.getElementById("sim-uv"),
  simVis: document.getElementById("sim-vis"),
  simLightning: document.getElementById("sim-lightning"),
  simDemoKids: document.getElementById("sim-demo-kids"),
  valSimTemp: document.getElementById("val-sim-temp"),
  valSimWind: document.getElementById("val-sim-wind"),
  valSimGusts: document.getElementById("val-sim-gusts"),
  valSimPrecip: document.getElementById("val-sim-precip"),
  valSimUv: document.getElementById("val-sim-uv"),
  valSimVis: document.getElementById("val-sim-vis"),
  simTriggeredCount: document.getElementById("sim-triggered-count"),
  simTriggeredList: document.getElementById("sim-triggered-list"),
  presetButtons: document.querySelectorAll(".btn-preset"),
  
  // Matrix Elements
  sopsMatrixContainer: document.getElementById("sops-matrix-container"),
  sopCountLabel: document.getElementById("sop-count-label"),
};

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  startClock();
  fetchSOPs();
  loadInitialAdvisory("Can I go cycling in London today?", "London", "cycling");
  runSimulation();
});

// Clock updater
function startClock() {
  function update() {
    const now = new Date();
    if (elements.liveClock) {
      elements.liveClock.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
  }
  update();
  setInterval(update, 1000);
}

// Event Listeners
function initEventListeners() {
  // Tab Switcher
  elements.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      switchTab(target);
    });
  });

  // Location Search
  elements.btnSearchCity.addEventListener("click", () => {
    const query = elements.cityInput.value.trim();
    if (query) {
      handleLocationChange(query);
    }
  });

  elements.cityInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const query = elements.cityInput.value.trim();
      if (query) {
        handleLocationChange(query);
      }
    }
  });

  // Geolocation
  elements.btnGeoDetect.addEventListener("click", () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const lat = position.coords.latitude;
          const lon = position.coords.longitude;
          try {
            const res = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${lat},${lon}&count=1`);
            handleLocationChange(`${lat.toFixed(2)}, ${lon.toFixed(2)}`);
          } catch (e) {
            handleLocationChange(`${lat.toFixed(2)}, ${lon.toFixed(2)}`);
          }
        },
        () => {
          alert("Could not access your location. Please type a city name.");
        }
      );
    } else {
      alert("Geolocation is not supported by your browser.");
    }
  });

  // Activity Chips
  elements.activityChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      elements.activityChips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.currentActivity = chip.getAttribute("data-activity");
      triggerAdvisoryQuery(`Check advisory for ${state.currentActivity} in ${state.currentLocation}`);
    });
  });

  // Demographic Checkboxes
  elements.demoCheckboxes.forEach((cb) => {
    cb.addEventListener("change", () => {
      state.vulnerableGroups = Array.from(elements.demoCheckboxes)
        .filter((c) => c.checked)
        .map((c) => c.value);
      triggerAdvisoryQuery(`Check advisory for ${state.currentActivity} in ${state.currentLocation}`);
    });
  });

  // Chat Form Submission
  elements.advisorForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = elements.chatUserInput.value.trim();
    if (query) {
      triggerAdvisoryQuery(query);
      elements.chatUserInput.value = "";
    }
  });

  // Suggestion Chips
  elements.suggestButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-query");
      if (q) {
        triggerAdvisoryQuery(q);
      }
    });
  });

  // Clear Chat
  elements.btnClearChat.addEventListener("click", () => {
    elements.chatMessages.innerHTML = `
      <div class="chat-bubble bot-bubble">
        <div class="bubble-header"><i class="fa-solid fa-robot"></i> <strong>AeroSOP Copilot</strong></div>
        <div class="bubble-content">
          <p>Conversation cleared. Ready for your next weather safety query!</p>
        </div>
      </div>
    `;
  });

  // Text-To-Speech
  elements.btnSpeak.addEventListener("click", () => {
    if (state.lastAdvisoryText && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const cleanText = state.lastAdvisoryText.replace(/[*_#>`~]/g, '');
      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  });

  // Voice Input (Speech Recognition)
  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
      state.isListening = true;
      elements.btnMic.classList.add("listening");
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      elements.chatUserInput.value = transcript;
      triggerAdvisoryQuery(transcript);
    };

    recognition.onend = () => {
      state.isListening = false;
      elements.btnMic.classList.remove("listening");
    };

    elements.btnMic.addEventListener("click", () => {
      if (state.isListening) {
        recognition.stop();
      } else {
        recognition.start();
      }
    });
  } else {
    elements.btnMic.style.display = "none";
  }

  // Simulator Controls Event Listeners
  const simControls = [
    elements.simTemp, elements.simWind, elements.simGusts,
    elements.simPrecip, elements.simUv, elements.simVis,
    elements.simActivitySelect, elements.simLightning, elements.simDemoKids
  ];

  simControls.forEach((ctrl) => {
    if (ctrl) {
      ctrl.addEventListener("input", () => {
        updateSimulatorLabels();
        runSimulation();
      });
      ctrl.addEventListener("change", () => {
        updateSimulatorLabels();
        runSimulation();
      });
    }
  });

  // Simulator Presets
  elements.presetButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const preset = btn.getAttribute("data-preset");
      applySimulatorPreset(preset);
    });
  });
}

function switchTab(tabId) {
  state.activeTab = tabId;
  elements.tabs.forEach((t) => {
    if (t.getAttribute("data-tab") === tabId) {
      t.classList.add("active");
    } else {
      t.classList.remove("active");
    }
  });

  elements.tabViews.forEach((view) => {
    if (view.id === tabId) {
      view.classList.add("active");
    } else {
      view.classList.remove("active");
    }
  });

  if (tabId === "tab-simulator") {
    runSimulation();
  }
}

function handleLocationChange(newLocation) {
  state.currentLocation = newLocation;
  elements.cityInput.value = newLocation;
  triggerAdvisoryQuery(`Check advisory for ${state.currentActivity} in ${newLocation}`, newLocation);
}

// Initial Advisory Request
async function loadInitialAdvisory(query, location, activity) {
  await triggerAdvisoryQuery(query, location, activity);
}

// Trigger Advisory Chat Query
async function triggerAdvisoryQuery(query, locationOverride = null, activityOverride = null) {
  appendUserMessage(query);

  const loadingBubble = appendBotLoadingMessage();

  try {
    const payload = {
      query: query,
      location: locationOverride || state.currentLocation,
      activity: activityOverride || state.currentActivity,
      vulnerable_groups: state.vulnerableGroups,
    };

    const res = await fetch(`${API_BASE}/api/advisor/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`Advisor API responded with status ${res.status}`);
    }

    const data = await res.json();
    loadingBubble.remove();

    renderAdvisoryData(data);
    appendBotAdvisoryMessage(data.advisory);

    // Save text for speech synthesis
    state.lastAdvisoryText = data.advisory.advisory_markdown;

    // Update location label
    if (data.location && data.location.name) {
      state.currentLocation = data.location.name;
      elements.currentLocationText.textContent = data.location.name;
    }
  } catch (err) {
    loadingBubble.remove();
    appendBotMessage(`⚠️ Error communicating with advisor engine: ${err.message}. Please try again.`);
  }
}

// Render Telemetry & Forecasts
function renderAdvisoryData(data) {
  const w = data.weather;
  const adv = data.advisory;

  if (w) {
    elements.currentTemp.textContent = w.temperature.toFixed(1);
    elements.apparentTemp.textContent = `${w.apparent_temperature.toFixed(1)}°C`;
    elements.weatherDesc.textContent = w.weather_description;
    elements.weatherIcon.textContent = getWeatherIcon(w.weather_code);

    elements.metricWind.textContent = `${w.wind_speed.toFixed(1)} km/h`;
    elements.metricGusts.textContent = `Gusts ${w.wind_gusts.toFixed(1)} km/h`;
    elements.metricPrecip.textContent = `${w.precipitation.toFixed(1)} mm`;
    elements.metricPrecipProb.textContent = `${w.precipitation_probability.toFixed(0)}% chance`;
    elements.metricUv.textContent = `${w.uv_index.toFixed(1)} (${getUVLabel(w.uv_index)})`;
    elements.metricVis.textContent = `${w.visibility.toFixed(1)} km`;
    elements.metricHumidity.textContent = `${w.relative_humidity.toFixed(0)}%`;
    elements.metricLightning.textContent = w.lightning_risk ? "⚡ ACTIVE RISK" : "None";
    elements.metricLightning.style.color = w.lightning_risk ? "#ef4444" : "#f1f5f9";
  }

  // Update Safety Gauge
  const score = adv.safety_score;
  elements.safetyScoreValue.textContent = score;

  // Arc length is ~126 (pi * 40)
  const offset = 126 - (score / 100) * 126;
  elements.gaugeFill.style.strokeDashoffset = offset;
  elements.gaugeFill.style.stroke = adv.risk_color || "#10b981";

  // Safety Status Badge
  elements.safetyStatusBadge.style.background = `${adv.risk_color}22`;
  elements.safetyStatusBadge.style.borderColor = adv.risk_color;
  elements.safetyStatusBadge.style.color = adv.risk_color;
  elements.safetyStatusText.textContent = adv.activity_status;

  // SOP Alert Banner Box
  if (adv.matched_sops && adv.matched_sops.length > 0) {
    const topSop = adv.matched_sops[0];
    const sevClass = topSop.severity.toLowerCase();

    elements.sopAlertBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> <span>${topSop.severity} SAFETY DIRECTIVE TRIGGERED</span>`;
    elements.sopAlertBadge.style.color = adv.risk_color;

    elements.sopAlertBody.innerHTML = `
      <div class="sop-directive-box ${sevClass}">
        <div class="sop-title-row">
          <span>[${topSop.id}] ${topSop.name}</span>
          <span style="color:${adv.risk_color}; font-weight:800;">${topSop.severity}</span>
        </div>
        <p><strong>Condition:</strong> ${topSop.matched_reasons.join("; ")}</p>
        <p><strong>Guideline:</strong> ${topSop.advisory}</p>
        <div class="sop-action-highlight">🚨 Required Action: ${topSop.action}</div>
      </div>
    `;
  } else {
    elements.sopAlertBadge.innerHTML = `<i class="fa-solid fa-shield-check"></i> <span>SAFETY NOMINAL</span>`;
    elements.sopAlertBadge.style.color = "#34d399";
    elements.sopAlertBody.innerHTML = `<p>No hazardous SOP violations detected for <strong>${state.currentActivity}</strong> in this area. Conditions are safe.</p>`;
  }

  // Hourly Forecast
  renderHourly(data.hourly_forecast);

  // Daily Forecast
  renderDaily(data.daily_forecast);

  // Gear Checklist
  renderGear(adv.gear_checklist);
}

function renderHourly(hourly) {
  if (!elements.hourlyForecastList || !hourly) return;
  elements.hourlyForecastList.innerHTML = "";

  hourly.slice(0, 16).forEach((h) => {
    const item = document.createElement("div");
    item.className = "hourly-item";
    item.innerHTML = `
      <div class="hourly-time">${h.time}</div>
      <div class="hourly-icon">${getWeatherIcon(h.weather_code)}</div>
      <div class="hourly-temp">${Math.round(h.temperature)}°</div>
      <div class="hourly-prob">${h.precip_prob}%</div>
    `;
    elements.hourlyForecastList.appendChild(item);
  });
}

function renderDaily(daily) {
  if (!elements.dailyForecastList || !daily) return;
  elements.dailyForecastList.innerHTML = "";

  daily.slice(0, 6).forEach((d) => {
    const item = document.createElement("div");
    item.className = "daily-item";
    const dateObj = new Date(d.date);
    const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

    item.innerHTML = `
      <div class="daily-date">${dayName}</div>
      <div class="daily-icon">${getWeatherIcon(d.weather_code)}</div>
      <div class="daily-temp-bar">
        <span class="daily-max">${Math.round(d.temp_max)}°</span>
        <span class="daily-min">${Math.round(d.temp_min)}°</span>
      </div>
      <div style="font-size:0.75rem; color:#38bdf8;">${d.precip_prob}% rain</div>
    `;
    elements.dailyForecastList.appendChild(item);
  });
}

function renderGear(gearList) {
  if (!elements.gearItemsList) return;
  elements.gearItemsList.innerHTML = "";
  if (!gearList || gearList.length === 0) {
    elements.gearItemsList.innerHTML = `<div class="gear-item-pill">Standard comfortable clothing</div>`;
    return;
  }
  gearList.forEach((item) => {
    const pill = document.createElement("div");
    pill.className = "gear-item-pill";
    pill.innerHTML = `<span>${item}</span>`;
    elements.gearItemsList.appendChild(pill);
  });
}

// Chat UI Appenders
function appendUserMessage(text) {
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble user-bubble";
  bubble.innerHTML = `
    <div class="bubble-header"><i class="fa-solid fa-user"></i> <strong>You</strong></div>
    <div class="bubble-content"><p>${escapeHtml(text)}</p></div>
  `;
  elements.chatMessages.appendChild(bubble);
  scrollChatBottom();
}

function appendBotMessage(text) {
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble bot-bubble";
  bubble.innerHTML = `
    <div class="bubble-header"><i class="fa-solid fa-robot"></i> <strong>AeroSOP Copilot</strong></div>
    <div class="bubble-content"><p>${text}</p></div>
  `;
  elements.chatMessages.appendChild(bubble);
  scrollChatBottom();
  return bubble;
}

function appendBotLoadingMessage() {
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble bot-bubble";
  bubble.innerHTML = `
    <div class="bubble-header"><i class="fa-solid fa-robot"></i> <strong>AeroSOP Copilot</strong></div>
    <div class="bubble-content"><p><i class="fa-solid fa-spinner fa-spin"></i> Consulting weather radar & evaluating safety SOPs...</p></div>
  `;
  elements.chatMessages.appendChild(bubble);
  scrollChatBottom();
  return bubble;
}

function appendBotAdvisoryMessage(advisory) {
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble bot-bubble";
  const htmlContent = parseMarkdownToHtml(advisory.advisory_markdown);

  bubble.innerHTML = `
    <div class="bubble-header"><i class="fa-solid fa-shield-halved"></i> <strong>Safety Advisory Directive</strong></div>
    <div class="bubble-content">${htmlContent}</div>
  `;
  elements.chatMessages.appendChild(bubble);
  scrollChatBottom();
}

function scrollChatBottom() {
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

// Simple Markdown Parser
function parseMarkdownToHtml(md) {
  if (!md) return "";
  let html = md
    .replace(/^### (.*$)/gim, '<h4>$1</h4>')
    .replace(/^## (.*$)/gim, '<h3>$1</h3>')
    .replace(/^# (.*$)/gim, '<h2>$1</h2>')
    .replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>')
    .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*)\*/gim, '<em>$1</em>')
    .replace(/`([^`]+)`/gim, '<code>$1</code>')
    .replace(/\n\n/gim, '</p><p>')
    .replace(/\n/gim, '<br />');

  return `<p>${html}</p>`;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// SIMULATOR LOGIC
function updateSimulatorLabels() {
  elements.valSimTemp.textContent = `${parseFloat(elements.simTemp.value).toFixed(1)}°C`;
  elements.valSimWind.textContent = `${elements.simWind.value} km/h`;
  elements.valSimGusts.textContent = `${elements.simGusts.value} km/h`;
  elements.valSimPrecip.textContent = `${parseFloat(elements.simPrecip.value).toFixed(1)} mm`;
  elements.valSimUv.textContent = `${parseFloat(elements.simUv.value).toFixed(1)}`;
  elements.valSimVis.textContent = `${parseFloat(elements.simVis.value).toFixed(1)} km`;
}

let simDebounceTimer = null;
function runSimulation() {
  clearTimeout(simDebounceTimer);
  simDebounceTimer = setTimeout(async () => {
    const act = elements.simActivitySelect.value;
    const temp = parseFloat(elements.simTemp.value);
    const wind = parseFloat(elements.simWind.value);
    const gusts = parseFloat(elements.simGusts.value);
    const precip = parseFloat(elements.simPrecip.value);
    const uv = parseFloat(elements.simUv.value);
    const vis = parseFloat(elements.simVis.value);
    const lightning = elements.simLightning.checked;
    const groups = elements.simDemoKids.checked ? ["children"] : [];

    let wCode = 0;
    if (lightning) wCode = 95;
    else if (precip >= 10) wCode = 65;
    else if (precip > 0.5) wCode = 61;

    try {
      const res = await fetch(`${API_BASE}/api/sop/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          activity: act,
          target_groups: groups,
          temperature: temp,
          wind_speed: wind,
          wind_gusts: gusts,
          precipitation: precip,
          uv_index: uv,
          visibility: vis,
          weather_code: wCode,
          lightning_risk: lightning,
        }),
      });

      if (!res.ok) throw new Error("Simulation failed");
      const data = await res.json();
      renderSimulationResults(data);
    } catch (e) {
      console.error(e);
    }
  }, 80);
}

function renderSimulationResults(data) {
  elements.simTriggeredCount.textContent = `${data.matched_count} SOP${data.matched_count === 1 ? '' : 's'} Triggered`;
  elements.simTriggeredList.innerHTML = "";

  if (data.matched_count === 0) {
    elements.simTriggeredList.innerHTML = `
      <div class="sim-empty-state">
        <i class="fa-solid fa-shield-heart"></i>
        <h4>Nominal Operating Conditions</h4>
        <p>No adverse safety rules triggered for <strong>${data.activity}</strong> under these environmental parameters.</p>
      </div>
    `;
    return;
  }

  data.matched_sops.forEach((sop) => {
    const card = document.createElement("div");
    card.className = `sim-sop-card sev-${sop.severity}`;
    card.innerHTML = `
      <div class="sim-sop-header">
        <span class="sim-sop-id">${sop.id}: ${sop.name}</span>
        <span class="sim-sop-badge">${sop.severity} (Priority ${sop.priority})</span>
      </div>
      <div class="sim-sop-triggers"><strong>Matched Conditions:</strong> ${sop.reasons.join("; ")}</div>
      <div class="sim-sop-advisory"><strong>Directive:</strong> ${sop.advisory}</div>
      <div style="font-weight:700; color:#fff; margin-top:0.4rem;">🚨 Required Action: ${sop.action}</div>
    `;
    elements.simTriggeredList.appendChild(card);
  });
}

function applySimulatorPreset(preset) {
  if (preset === "thunderstorm") {
    elements.simTemp.value = 22;
    elements.simWind.value = 45;
    elements.simGusts.value = 65;
    elements.simPrecip.value = 20;
    elements.simUv.value = 1;
    elements.simVis.value = 2;
    elements.simLightning.checked = true;
  } else if (preset === "heatwave") {
    elements.simTemp.value = 42;
    elements.simWind.value = 10;
    elements.simGusts.value = 15;
    elements.simPrecip.value = 0;
    elements.simUv.value = 11;
    elements.simVis.value = 10;
    elements.simLightning.checked = false;
  } else if (preset === "highwind") {
    elements.simTemp.value = 16;
    elements.simWind.value = 48;
    elements.simGusts.value = 70;
    elements.simPrecip.value = 2;
    elements.simUv.value = 3;
    elements.simVis.value = 8;
    elements.simLightning.checked = false;
  } else if (preset === "freezing") {
    elements.simTemp.value = -14;
    elements.simWind.value = 30;
    elements.simGusts.value = 45;
    elements.simPrecip.value = 0.5;
    elements.simUv.value = 1;
    elements.simVis.value = 4;
    elements.simLightning.checked = false;
  } else if (preset === "clear") {
    elements.simTemp.value = 23;
    elements.simWind.value = 12;
    elements.simGusts.value = 16;
    elements.simPrecip.value = 0;
    elements.simUv.value = 4.5;
    elements.simVis.value = 12;
    elements.simLightning.checked = false;
  }
  updateSimulatorLabels();
  runSimulation();
}

// Fetch and Render SOP Matrix
async function fetchSOPs() {
  try {
    const res = await fetch(`${API_BASE}/api/sops`);
    if (res.ok) {
      const data = await res.json();
      state.sopsList = data.sops;
      if (elements.sopCountLabel) {
        elements.sopCountLabel.textContent = `${data.total} Active SOPs`;
      }
      renderSOPMatrix(data.sops);
    }
  } catch (e) {
    console.error("Failed to load SOPs:", e);
  }
}

function renderSOPMatrix(sops) {
  if (!elements.sopsMatrixContainer) return;
  elements.sopsMatrixContainer.innerHTML = "";

  sops.forEach((sop) => {
    const card = document.createElement("div");
    card.className = "matrix-sop-card";

    const actPills = sop.activities.map((a) => `<span class="matrix-act-pill">${a}</span>`).join("");
    const condJson = JSON.stringify(sop.conditions, null, 2);

    card.innerHTML = `
      <div class="matrix-card-top">
        <span class="matrix-sop-id">${sop.id}</span>
        <span class="sim-sop-badge" style="background:${getSeverityBadgeBg(sop.severity)}; color:${getSeverityBadgeText(sop.severity)};">
          ${sop.severity} | Priority ${sop.priority}
        </span>
      </div>
      <div class="matrix-sop-name">${sop.name}</div>
      <div class="matrix-category-tag">Category: ${sop.category}</div>
      <div class="matrix-activities-wrap">${actPills}</div>
      <pre class="matrix-condition-code"><code>${condJson}</code></pre>
      <div class="matrix-action-box">
        <strong>Mandatory Directive:</strong> ${sop.advisory}
      </div>
    `;
    elements.sopsMatrixContainer.appendChild(card);
  });
}

function getSeverityBadgeBg(sev) {
  if (sev === "CRITICAL") return "rgba(239, 68, 68, 0.2)";
  if (sev === "HIGH") return "rgba(249, 115, 22, 0.2)";
  if (sev === "MEDIUM") return "rgba(234, 179, 8, 0.2)";
  return "rgba(59, 130, 246, 0.2)";
}

function getSeverityBadgeText(sev) {
  if (sev === "CRITICAL") return "#fca5a5";
  if (sev === "HIGH") return "#fdba74";
  if (sev === "MEDIUM") return "#fde047";
  return "#93c5fd";
}

function getWeatherIcon(code) {
  const icons = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
    45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌦️", 55: "🌧️",
    61: "🌦️", 63: "🌧️", 65: "🌧️",
    71: "🌨️", 73: "🌨️", 75: "❄️",
    80: "🌦️", 81: "🌧️", 82: "⛈️",
    95: "⚡", 96: "⛈️", 99: "⛈️"
  };
  return icons[code] || "🌤️";
}

function getUVLabel(uv) {
  if (uv <= 2) return "Low";
  if (uv <= 5) return "Mod";
  if (uv <= 7) return "High";
  if (uv <= 10) return "Very High";
  return "Extreme";
}
