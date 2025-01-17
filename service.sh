#!/bin/bash

input="$1"
IFS=',' read -r first second <<< "$input"
num_instances=$first
num_cards=$second

# 检查是否传递了 "close" 参数
if [ "$2" == "close" ]; then
    echo "Stopping all background services..."
    pkill -f stressTest.service  # 根据实际服务名，终止所有后台服务
    echo "All services stopped."
    exit 0
fi

echo "First: $num_instances"
echo "Second: $num_cards"

# 创建服务配置
services=()
for ((i = 0; i < num_instances; i++)); do
    if [ "$num_cards" -eq 1 ]; then
        card_id=0
    else
        card_id=$((i % num_cards))
    fi

    server_ip="localhost"
    server_port=$((9990 + i + 1))
    output_raw="./output/$((i + 1))_cuda${card_id}_{raw}.raw"
    device="cuda:${card_id}"

    # 将服务信息存储为字符串并添加到数组
    service="server_ip=$server_ip server_port=$server_port output_raw=$output_raw device=$device"
    services+=("$service")
done

# 启动服务
for service in "${services[@]}"; do
    echo $service
    nohup python -m stressTest.service $service &
    sleep 2
done
