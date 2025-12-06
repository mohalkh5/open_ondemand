# Wait for the chainlit server to start
echo "Waiting for chainlit server to open port ${port}..."
echo "TIMING - Starting wait at: $(date)"
if wait_until_port_used "${host}:${port}" 600; then
  echo "Discovered chainlit server listening on port ${port}!"
  echo "TIMING - Wait ended at: $(date)"
else
  echo "Timed out waiting for chainlit server to open port ${port}!"
  echo "TIMING - Wait ended at: $(date)"
  pkill -P ${SCRIPT_PID}
  clean_up 1
fi
sleep 4
