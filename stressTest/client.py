import socket
import asyncio
import time
import sys
import subprocess

from stressTest.tools import *


async def listen_to_voice(text, idx, server_ip='localhost', server_port=9999, rate=24000, output_file="./out.wav", stats=None):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_ip, server_port))

    buffer_data = b''
    start_time = time.time()

    async def play_audio_stream():
        nonlocal buffer_data

        buffer = b''
        buffer_size = 4096

        try:
            while True:
                chunk = await asyncio.get_event_loop().run_in_executor(None, client_socket.recv, 1024)

                if not chunk:  # End of stream
                    break

                if b"END_OF_AUDIO" in chunk:
                    buffer += chunk.replace(b"END_OF_AUDIO", b"")
                    if buffer:
                        buffer_data += buffer
                    break

                buffer += chunk

                if len(buffer) >= buffer_size:
                    buffer_data += buffer[:buffer_size]
                    buffer = buffer[buffer_size:]
        finally:
            pass

    try:
        await asyncio.get_event_loop().run_in_executor(None, client_socket.sendall, text.encode('utf-8'))
        await play_audio_stream()

        response_time = time.time() - start_time
        stats['response_times'].append(response_time)
        stats['success_count'] += 1

        with open(output_file, "wb") as f:
            f.write(buffer_data)

        print(f"[DEBUG] {idx} idx save ok (response time: {response_time:.2f}s)")

    except Exception as e:
        print(f"Error in listen_to_voice: {e}")
        stats['failure_count'] += 1

    finally:
        client_socket.close()


def get_gpu_stats():
    """Retrieve GPU usage stats using nvidia-smi."""
    try:
        output = subprocess.check_output(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"]).decode()
        gpu_stats = [line.split(",") for line in output.strip().split("\n")]
        return [{"gpu_load": int(stat[0]), "memory_used": int(stat[1])} for stat in gpu_stats]
    except Exception as e:
        print(f"Error retrieving GPU stats: {e}")
        return []


async def main(services, eruption):
    test_reqs = [
        "你认为，抱歉，我们没有工号",
        "现在浦，你还有什么想说的吗",
        "呃，账，通话是有录音的，请注意您的态度，我们对您的情况如实反馈，希望你能积极配合处理此事。",
        "合约明，你是想协商什么？现在要和你了解一些信息，可以吗。",
    ]

    stats = {
        "response_times": [],
        "success_count": 0,
        "failure_count": 0,
        "gpu_stats": [],
    }

    semaphore = asyncio.Semaphore(int(eruption))  # 限制并发数量

    async def limited_listen_to_voice(idx, text):
        service = services[idx % len(services)]
        output_file = service['output_raw'].format(idx)
        async with semaphore:
            await listen_to_voice(
                text=text,
                idx=idx,
                server_ip=service["server_ip"],
                server_port=service["server_port"],
                output_file=output_file,
                stats=stats
            )

    # 将协程对象包装成任务
    tasks = [asyncio.create_task(limited_listen_to_voice(idx, text)) for idx, text in enumerate(test_reqs)]

    # GPU stats monitoring in parallel
    async def monitor_gpu():
        while not all(task.done() for task in tasks):
            gpu_data = get_gpu_stats()
            stats['gpu_stats'].append(gpu_data)
            await asyncio.sleep(1)   # 每隔1秒采样一次GPU信息


    start_time = time.time()
    await asyncio.gather(monitor_gpu(), asyncio.gather(*tasks))   # 并行执行任务
    total_time = time.time() - start_time


    print("[DEBUG] total_time: ", total_time)
    print("[DEBUG] sum(stats['response_times']): ", sum(stats['response_times']))

    # 计算吞吐量、平均响应时间、GPU负载峰值、显存占用峰值
    avg_response_time = sum(stats['response_times']) / len(stats['response_times'])                                     # 平均响应时间：平均每个请求的耗时
    throughput = len(test_reqs) / total_time                                                                            # 吞吐量：每秒完成的请求数量，吞吐量≈并发数÷平均响应时间
    gpu_peak = max((max(gpu['gpu_load'] for gpu in gpu_stats) for gpu_stats in stats['gpu_stats']), default=0)          # GPU负载峰值
    memory_peak = max((max(gpu['memory_used'] for gpu in gpu_stats) for gpu_stats in stats['gpu_stats']), default=0)    # 显存占用峰值

    # GPU平均负载计算
    total_gpu_load = sum(sum(gpu['gpu_load'] for gpu in gpu_stats) for gpu_stats in stats['gpu_stats'])
    total_samples = sum(len(gpu_stats) for gpu_stats in stats['gpu_stats'])
    gpu_average_load = total_gpu_load / total_samples

    print(f"[STATS] 平均响应时间: {avg_response_time:.2f} 秒")
    print(f"[STATS] 吞吐量: {throughput:.2f} 请求/秒")
    print(f"[STATS] 成功率: {stats['success_count'] / len(test_reqs) * 100:.2f}%")
    print(f"[STATS] GPU 负载均值: {gpu_average_load:.2f}%")
    print(f"[STATS] GPU 负载峰值: {gpu_peak}%")
    print(f"[STATS] GPU 显存峰值: {memory_peak} MB")

    print("[DEBUG] stats['response_times']: ", stats['response_times'])

if __name__ == "__main__":
    instance_config = sys.argv[1]
    eruption = sys.argv[2]

    services = parse_instance_config(instance_config)
    print("[DEBUG] 服务配置:", services)

    asyncio.run(main(services, eruption))



