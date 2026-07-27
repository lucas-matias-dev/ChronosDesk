#include "WiFiService.h"

#include <Network.h>
#include <WiFi.h>

#include "../config/AppConfig.h"
#include "../config/Secrets.h"
#include "../diagnostics/ResourceMonitor.h"

void WiFiService::begin() {
  Network.begin();
  WiFi.STA.begin();
  WiFi.mode(WIFI_STA);
  requestConnection(millis());
}

void WiFiService::update(uint32_t nowMs) {
  if (WiFi.STA.hasIP()) {
    if (state_ != WiFiConnectionState::Connected) {
      const bool wasReconnect = hasConnectedBefore_;
      Network.setDefaultInterface(WiFi.STA);
      setState(WiFiConnectionState::Connected);
      hasConnectedBefore_ = true;
      Serial.print("[WIFI] Conectado. IP: ");
      Serial.println(WiFi.STA.localIP());
      if (wasReconnect) {
        ResourceMonitor::recordWiFiReconnect();
      }
      ResourceMonitor::checkpoint(
          wasReconnect ? "wifi:reconnected" : "wifi:connected");
    }
    return;
  }

  if (state_ == WiFiConnectionState::Connected) {
    setState(WiFiConnectionState::Disconnected);
    Serial.println("[WIFI] Conexao perdida");
    ResourceMonitor::checkpoint("wifi:disconnected");
  }

  const uint32_t timeSinceAttempt = nowMs - lastConnectionAttemptMs_;
  if (state_ == WiFiConnectionState::Connecting &&
      timeSinceAttempt >= AppConfig::Network::connectionTimeoutMs) {
    setState(WiFiConnectionState::Disconnected);
    Serial.println("[WIFI] Tentativa expirou; operando em modo degradado");
  }

  if (state_ == WiFiConnectionState::Disconnected &&
      timeSinceAttempt >= AppConfig::Network::reconnectIntervalMs) {
    requestConnection(nowMs);
  }
}

bool WiFiService::isConnected() const {
  return state_ == WiFiConnectionState::Connected;
}

bool WiFiService::stateChanged() {
  const bool changed = stateChanged_;
  stateChanged_ = false;
  return changed;
}

WiFiConnectionState WiFiService::state() const {
  return state_;
}

void WiFiService::requestConnection(uint32_t nowMs) {
  lastConnectionAttemptMs_ = nowMs;
  setState(WiFiConnectionState::Connecting);
  Serial.println("[WIFI] Tentando conectar");

  if (!WiFi.STA.connect(configuredWiFiSsid, configuredWiFiPassword)) {
    setState(WiFiConnectionState::Disconnected);
    Serial.println("[WIFI] Nao foi possivel iniciar a tentativa");
  }
}

void WiFiService::setState(WiFiConnectionState newState) {
  if (state_ == newState) {
    return;
  }
  state_ = newState;
  stateChanged_ = true;
}
