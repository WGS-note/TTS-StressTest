import socket
import threading
from threading import Thread
import time
import gc
import traceback
import sys

from stressTest.tools import *
from stressTest.logging import *


def handle_client(client_socket, processor, logger):
    try:
        while True:
            data = client_socket.recv(1024).decode("utf-8")
            if not data:
                break

            try:
                text = data.strip()

                for audio_chunk in processor.generate_stream(text):
                    client_socket.sendall(audio_chunk)

                client_socket.sendall(b"END_OF_AUDIO")

            except Exception as inner_e:
                logger.info(f"Error during processing: {inner_e}")
                traceback.print_exc()
                break

    except Exception as e:
        logger.info(f"Error handling client: {e}")
        traceback.print_exc()
    finally:
        client_socket.close()


def start_server(host, port, processor, logger):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(5)
    logger.info(f"Server listening on {host}:{port}")

    while True:
        client_socket, addr = server.accept()
        logger.info(f"Accepted connection from {addr}")
        client_handler = Thread(target=handle_client, args=(client_socket, processor, logger))
        client_handler.start()


def start_server_thread(host, port, processor, logger):
    thread = threading.Thread(target=start_server, args=(host, port, processor, logger))
    thread.daemon = True  # 确保线程在主程序退出时终止
    thread.start()
    return thread


if __name__ == "__main__":

    ckpt_file = "/home/wangguisen/projects/tts/F5-TTS/ckpts/F5TTS_Base/model_1200000.safetensors"
    vocab_file = "/home/wangguisen/projects/tts/F5-TTS/src/f5_tts/infer/examples/vocab.txt"
    ref_audio = "/home/wangguisen/projects/tts/test_audio/1_wgs-f5tts.wav"
    ref_text = "那到时候再给你打电话，麻烦你注意接听。"
    vocoder_name = "vocos"
    vocoder_local_path = "/home/wangguisen/projects/tts/F5-TTS/ckpts/vocos-mel-24khz"

    # 实例数量
    instance_config = sys.argv[1]
    services = parse_instance_config(instance_config)

    try:
        threads = []  # 保存所有线程

        for service in services:

            logger = configure_logger(service_id=service["server_port"], log_dir="./logs")
            logger.info(f"Services: {services}")

            processor = TTSStreamingProcessor(
                ckpt_file=ckpt_file,
                vocab_file=vocab_file,
                ref_audio=ref_audio,
                ref_text=ref_text,
                dtype=torch.float32,
                vocoder_name=vocoder_name,
                vocoder_local_path=vocoder_local_path,
                device=service["device"],
            )

            thread = start_server_thread(service["server_ip"], service["server_port"], processor, logger)
            threads.append(thread)
            time.sleep(3)

        # 等待所有线程运行（主程序保持活跃）
        for thread in threads:
            thread.join()

    except KeyboardInterrupt:
        gc.collect()




