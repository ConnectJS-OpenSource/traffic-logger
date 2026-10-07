#!/bin/bash

SERVER_URL="http://dlptest.com/api/http-post/"
TEST_FILE="/tmp/latency-test.bin"
INTERVAL=0
CONNECT_TIMEOUT=10
MAX_TIME=60
LOG_FILE="./upload-latency.log"

cleanup() {
    echo
    echo "$(date '+%F %T') - Stopped by user"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Create 1MB test file if missing
if [ ! -f "$TEST_FILE" ]; then
    echo "Creating test file..."
    dd if=/dev/urandom of="$TEST_FILE" bs=1M count=1 status=none
fi

echo "================================================="
echo "Upload Latency Monitor Started"
echo "Server : $SERVER_URL"
echo "Interval : ${INTERVAL}s"
echo "Log File : $LOG_FILE"
echo "Press Ctrl+C to stop"
echo "================================================="

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    RESULT=$(
        curl \
            --silent \
            --show-error \
            --output /dev/null \
            --connect-timeout "$CONNECT_TIMEOUT" \
            --max-time "$MAX_TIME" \
            --write-out "%{time_total},%{http_code}" \
            --request POST \
            --data-binary @"$TEST_FILE" \
            "$SERVER_URL" 2>/dev/null
    )

    CURL_EXIT=$?

    if [ $CURL_EXIT -eq 0 ]; then
        LATENCY_SEC=$(echo "$RESULT" | cut -d',' -f1)
        HTTP_CODE=$(echo "$RESULT" | cut -d',' -f2)

        LATENCY_MS=$(awk "BEGIN { printf \"%.0f\", $LATENCY_SEC * 1000 }")

        if [[ "$HTTP_CODE" =~ ^2|3 ]]; then
            STATUS="OK"
        else
            STATUS="HTTP_ERROR"
        fi

        echo "$TIMESTAMP | $STATUS | ${LATENCY_MS} ms | HTTP $HTTP_CODE" | tee -a "$LOG_FILE"
    else
        case $CURL_EXIT in
            6)  ERROR="DNS_FAILURE" ;;
            7)  ERROR="CONNECTION_REFUSED" ;;
            28) ERROR="TIMEOUT" ;;
            35) ERROR="SSL_ERROR" ;;
            52) ERROR="EMPTY_RESPONSE" ;;
            *)  ERROR="CURL_ERROR_$CURL_EXIT" ;;
        esac

        echo "$TIMESTAMP | FAILED | $ERROR" | tee -a "$LOG_FILE"
    fi

    sleep "$INTERVAL"
done
