#include "SpotifyPlayback.h"

#include <cstring>

void SpotifyPlayback::clear() {
  memset(itemId, 0, sizeof(itemId));
  memset(title, 0, sizeof(title));
  memset(artists, 0, sizeof(artists));
  contentType = SpotifyContentType::None;
  durationMs = 0;
  progressMs = 0;
  progressUpdatedAtMs = 0;
  isPlaying = false;
  hasItem = false;
}

void SpotifyPlayback::advanceProgress(uint32_t nowMs) {
  if (!hasItem || !isPlaying) {
    progressUpdatedAtMs = nowMs;
    return;
  }

  const uint32_t elapsed = nowMs - progressUpdatedAtMs;
  progressUpdatedAtMs = nowMs;
  progressMs = min(progressMs + elapsed, durationMs);
}
