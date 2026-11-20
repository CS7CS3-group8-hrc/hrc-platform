#!/usr/bin/env bash
# 1) Send "hello" to each service over HTTP and print its reply.
# 2) Show the messages that went through Kafka.
COMPOSE="docker compose -f docker-compose.agents.yml"

for port in 8101 8102 8103 8104 8105 8106 8107; do
  curl -s -X POST -d "hello" "http://localhost:$port"; echo
done

sleep 3   # give the consumers a moment to process

show() {
  echo; echo "=== Kafka topic: $1 ==="
  $COMPOSE exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 --topic "$1" --from-beginning --timeout-ms 5000 2>/dev/null
}
show hrc.hello.requests
show hrc.hello.replies
echo; echo "Service logs:  $COMPOSE logs allocation-coordinator ambulance-coordination-agent patient-transfer-agent | grep -E 'CONSUMED|produced'"
echo "Kafka UI:      http://localhost:8090"
