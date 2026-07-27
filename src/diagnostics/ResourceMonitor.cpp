#include "ResourceMonitor.h"

#if ENABLE_RESOURCE_DIAGNOSTICS

#include <Esp.h>
#include <esp_heap_caps.h>
#include <esp_partition.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <nvs.h>

namespace {
constexpr uint32_t summaryIntervalMs = 60000;
constexpr size_t maximumTaskCount = 32;

uint32_t lastSummaryMs = 0;
uint32_t wifiReconnectCount = 0;
uint32_t spotifyRequestCount = 0;
uint32_t spotifyFailureCount = 0;
uint32_t httpErrorCount = 0;

void printQuantity(const char* label, uint32_t bytes) {
  Serial.printf(
      "[RESOURCE] %s=%lu B (%.2f KiB, %.3f MiB)\n",
      label,
      static_cast<unsigned long>(bytes),
      bytes / 1024.0,
      bytes / (1024.0 * 1024.0));
}

void printMemoryRegion(const char* name, uint32_t capabilities) {
  const uint32_t total = heap_caps_get_total_size(capabilities);
  const uint32_t free = heap_caps_get_free_size(capabilities);
  const uint32_t minimum = heap_caps_get_minimum_free_size(capabilities);
  const uint32_t largest = heap_caps_get_largest_free_block(capabilities);
  const uint32_t used = total >= free ? total - free : 0;
  const double usedPercent = total == 0 ? 0.0 : used * 100.0 / total;
  const double continuityPercent =
      free == 0 ? 0.0 : largest * 100.0 / free;

  Serial.printf(
      "[RESOURCE] region=%s total=%lu free=%lu used=%lu used_pct=%.1f "
      "min_free=%lu largest=%lu largest_free_ratio_pct=%.1f\n",
      name,
      static_cast<unsigned long>(total),
      static_cast<unsigned long>(free),
      static_cast<unsigned long>(used),
      usedPercent,
      static_cast<unsigned long>(minimum),
      static_cast<unsigned long>(largest),
      continuityPercent);
}

void printTasks() {
  static TaskStatus_t tasks[maximumTaskCount] {};
  uint32_t totalRuntime = 0;
  const UBaseType_t taskCount =
      uxTaskGetSystemState(tasks, maximumTaskCount, &totalRuntime);
  Serial.printf(
      "[RESOURCE][TASKS] listed=%u system_count=%u capacity=%u\n",
      static_cast<unsigned>(taskCount),
      static_cast<unsigned>(uxTaskGetNumberOfTasks()),
      static_cast<unsigned>(maximumTaskCount));
  for (UBaseType_t index = 0; index < taskCount; ++index) {
    Serial.printf(
        "[RESOURCE][TASK] name=%s priority=%u core=%d stack_min_free=%u\n",
        tasks[index].pcTaskName,
        static_cast<unsigned>(tasks[index].uxCurrentPriority),
        static_cast<int>(tasks[index].xCoreID),
        static_cast<unsigned>(tasks[index].usStackHighWaterMark));
  }
  Serial.printf(
      "[RESOURCE][TASK] project=loopTask configured_stack=%u "
      "current_min_free=%u core=%d priority=%u\n",
      static_cast<unsigned>(getArduinoLoopTaskStackSize()),
      static_cast<unsigned>(uxTaskGetStackHighWaterMark(nullptr)),
      static_cast<int>(xPortGetCoreID()),
      static_cast<unsigned>(uxTaskPriorityGet(nullptr)));
}

void printPartitions() {
  esp_partition_iterator_t iterator =
      esp_partition_find(ESP_PARTITION_TYPE_ANY,
                         ESP_PARTITION_SUBTYPE_ANY,
                         nullptr);
  while (iterator != nullptr) {
    const esp_partition_t* partition = esp_partition_get(iterator);
    Serial.printf(
        "[RESOURCE][PARTITION] label=%s type=0x%02x subtype=0x%02x "
        "address=0x%08lx size=%lu encrypted=%s\n",
        partition->label,
        partition->type,
        partition->subtype,
        static_cast<unsigned long>(partition->address),
        static_cast<unsigned long>(partition->size),
        partition->encrypted ? "true" : "false");
    iterator = esp_partition_next(iterator);
  }
}

void printNvsStats() {
  nvs_stats_t stats {};
  const esp_err_t result = nvs_get_stats(nullptr, &stats);
  if (result != ESP_OK) {
    Serial.printf("[RESOURCE][NVS] unavailable error=%d\n", result);
    return;
  }
  Serial.printf(
      "[RESOURCE][NVS] used_entries=%lu free_entries=%lu "
      "total_entries=%lu namespaces=%lu\n",
      static_cast<unsigned long>(stats.used_entries),
      static_cast<unsigned long>(stats.free_entries),
      static_cast<unsigned long>(stats.total_entries),
      static_cast<unsigned long>(stats.namespace_count));
}
}  // namespace

void ResourceMonitor::begin() {
  Serial.println("[RESOURCE] diagnostics=enabled");
  Serial.printf(
      "[RESOURCE][CHIP] model=%s revision=%u cores=%u cpu_mhz=%lu "
      "sdk=%s core=%s\n",
      ESP.getChipModel(),
      ESP.getChipRevision(),
      ESP.getChipCores(),
      static_cast<unsigned long>(ESP.getCpuFreqMHz()),
      ESP.getSdkVersion(),
      ESP.getCoreVersion());
  printQuantity("flash_physical", ESP.getFlashChipSize());
  printQuantity("sketch_size", ESP.getSketchSize());
  printQuantity("sketch_partition_free", ESP.getFreeSketchSpace());
  printQuantity("heap_total", ESP.getHeapSize());
  printQuantity("heap_free", ESP.getFreeHeap());
  printQuantity("heap_min_free", ESP.getMinFreeHeap());
  printQuantity("heap_max_alloc", ESP.getMaxAllocHeap());
  printQuantity("psram_total", ESP.getPsramSize());
  printQuantity("psram_free", ESP.getFreePsram());
  printQuantity("psram_min_free", ESP.getMinFreePsram());
  printQuantity("psram_max_alloc", ESP.getMaxAllocPsram());
  printPartitions();
  printNvsStats();
  printTasks();
  checkpoint("setup:start");
}

void ResourceMonitor::update(uint32_t nowMs) {
  if (nowMs - lastSummaryMs < summaryIntervalMs) {
    return;
  }
  lastSummaryMs = nowMs;
  checkpoint("periodic:60s");
  Serial.printf(
      "[RESOURCE][COUNTERS] wifi_reconnects=%lu spotify_requests=%lu "
      "spotify_failures=%lu http_errors=%lu\n",
      static_cast<unsigned long>(wifiReconnectCount),
      static_cast<unsigned long>(spotifyRequestCount),
      static_cast<unsigned long>(spotifyFailureCount),
      static_cast<unsigned long>(httpErrorCount));
  printTasks();
  printNvsStats();
}

void ResourceMonitor::checkpoint(const char* name) {
  Serial.printf("[RESOURCE][CHECKPOINT] name=%s uptime_ms=%lu\n",
                name,
                static_cast<unsigned long>(millis()));
  printMemoryRegion("internal_8bit", MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
  printMemoryRegion("spiram_8bit", MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  printMemoryRegion("all_8bit", MALLOC_CAP_8BIT);
}

void ResourceMonitor::recordWiFiReconnect() {
  ++wifiReconnectCount;
}

void ResourceMonitor::recordSpotifyRequest() {
  ++spotifyRequestCount;
}

void ResourceMonitor::recordSpotifyFailure() {
  ++spotifyFailureCount;
}

void ResourceMonitor::recordHttpStatus(int statusCode) {
  if (statusCode < 0 || statusCode >= 400) {
    ++httpErrorCount;
  }
}

#endif
