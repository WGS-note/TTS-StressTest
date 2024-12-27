import subprocess


def parse_instance_config(instance_config):
    """
    解析实例配置字符串，例如 "2*1" 表示 2 个实例部署在 1 个卡上。
    返回一个列表，其中每个元素表示一个服务配置。
    """
    num_instances, num_cards = map(int, instance_config.split(','))
    services = []
    for i in range(num_instances):
        if num_cards == 1:
            card_id = 0
        else:
            card_id = i % num_cards

        services.append({
            "server_ip": "localhost",
            "server_port": 9990 + (i+1),  # 端口号递增
            "output_raw": f"./output/{i+1}_cuda{card_id}_{{}}.raw",  # 第几个实例_第几个卡_{}.raw
            "device": f"cuda:{card_id}",
        })

    return services, num_instances, num_cards


def parse_args(args):
    """解析 key=value 格式的命令行参数"""
    parsed_args = {}
    for arg in args:
        if '=' in arg:
            key, value = arg.split('=', 1)

            if "{raw}" in value:
                value = value.replace("{raw}", "{}")

            if "server_port" in key:
                value = int(value)

            parsed_args[key] = value
    return parsed_args


def get_gpu_stats():
    """Retrieve GPU usage stats using nvidia-smi."""
    try:
        output = subprocess.check_output(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"]).decode()
        gpu_stats = [line.split(",") for line in output.strip().split("\n")]
        return [{"gpu_load": int(stat[0]), "memory_used": int(stat[1])} for stat in gpu_stats]
    except Exception as e:
        print(f"Error retrieving GPU stats: {e}")
        return []