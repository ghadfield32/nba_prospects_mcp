#!/bin/bash
# LNB API: Get competitions by player
# Endpoint: POST /competition/getCompetitionByPlayer
# Usage: bash tools/lnb/curl_competitions_by_player.sh
# Example parameters: year=2025, person_external_id=3586

curl 'https://api-prod.lnb.fr/competition/getCompetitionByPlayer' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'accept-language: en-US,en;q=0.9' \
  -H 'accept-encoding: gzip, deflate, br, zstd' \
  -H 'cache-control: no-cache' \
  -H 'pragma: no-cache' \
  -H 'content-type: application/json' \
  -H 'language_code: fr' \
  -H 'origin: https://lnb.fr' \
  -H 'priority: u=1, i' \
  -H 'referer: https://lnb.fr/fr' \
  -H 'sec-ch-ua: "Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "Windows"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-site' \
  -H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36' \
  --data-raw '{"year":2025,"person_external_id":3586}' \
  --compressed
