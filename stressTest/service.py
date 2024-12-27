import multiprocessing
import socket
import time
import gc
import traceback
import sys
from threading import Thread
import json

import torch
from stressTest.tools import *
from stressTest.logging import *
from stressTest.model import TTSStreamingProcessor


def handle_client(client_socket, processor):
    try:
        while True:
            # Receive data from the client
            data = client_socket.recv(1024).decode("utf-8")
            if not data:
                break

            try:
                # The client sends the text input
                text = data.strip()

                # Generate and stream audio chunks
                for audio_chunk in processor.generate_stream(text):
                    client_socket.sendall(audio_chunk)

                # Send end-of-audio signal
                client_socket.sendall(b"END_OF_AUDIO")

            except Exception as inner_e:
                print(f"Error during processing: {inner_e}")
                traceback.print_exc()  # Print the full traceback to diagnose the issue
                break

    except Exception as e:
        print(f"Error handling client: {e}")
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
        client_handler = Thread(target=handle_client, args=(client_socket, processor))
        client_handler.start()


if __name__ == "__main__":

    ckpt_file = "/home/wangguisen/projects/tts/F5-TTS/ckpts/F5TTS_Base/model_1200000.safetensors"
    vocab_file = "/home/wangguisen/projects/tts/F5-TTS/src/f5_tts/infer/examples/vocab.txt"  # Add vocab file path if needed
    ref_audio = "/home/wangguisen/projects/tts/test_audio/1_wgs-f5tts.wav"
    ref_text = "那到时候再给你打电话，麻烦你注意接听。"
    vocoder_name = "vocos"
    vocoder_local_path = "/home/wangguisen/projects/tts/F5-TTS/ckpts/vocos-mel-24khz"

    service = parse_args(sys.argv[1:])

    logger = configure_logger(service_id=service["server_port"], log_dir="./logs")
    logger.info(f"Service: {service}")

    try:
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

        start_server(service["server_ip"], service["server_port"], processor, logger)

    except KeyboardInterrupt:
        gc.collect()
