import time
import struct
import torch
import torchaudio
from f5_tts.infer.utils_infer import infer_batch_process, preprocess_ref_audio_text, load_vocoder, load_model
from f5_tts.model.backbones.dit import DiT


class TTSStreamingProcessor:
    def __init__(self, ckpt_file, vocab_file, ref_audio, ref_text, vocoder_name, vocoder_local_path, device=None, dtype=torch.float32):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # Load the model using the provided checkpoint and vocab files
        self.model = load_model(
            model_cls=DiT,
            model_cfg=dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4),
            ckpt_path=ckpt_file,
            mel_spec_type="vocos",  # or "bigvgan" depending on vocoder
            vocab_file=vocab_file,
            ode_method="euler",
            use_ema=True,
            device=self.device,
        ).to(self.device, dtype=dtype)

        # Load the vocoder
        # self.vocoder = load_vocoder(is_local=False)
        self.vocoder_name = vocoder_name
        self.vocoder_local_path = vocoder_local_path
        self.vocoder = load_vocoder(vocoder_name=self.vocoder_name, is_local=True, local_path=self.vocoder_local_path, device=self.device)

        # Set sampling rate for streaming
        self.sampling_rate = 24000  # Consistency with client

        # Set reference audio and text
        self.ref_audio = ref_audio
        self.ref_text = ref_text

        # Warm up the model
        self._warm_up()

    def _warm_up(self):
        """Warm up the model with a dummy input to ensure it's ready for real-time processing."""
        print("Warming up the model...")
        ref_audio, ref_text = preprocess_ref_audio_text(self.ref_audio, self.ref_text)
        audio, sr = torchaudio.load(ref_audio)
        gen_text = "Warm-up text for the model."

        # Pass the vocoder as an argument here
        infer_batch_process((audio, sr), ref_text, [gen_text], self.model, self.vocoder, device=self.device)
        # warm_audio_chunk, warm_final_sample_rate, _  = infer_batch_process((audio, sr), ref_text, [gen_text], self.model, self.vocoder, device=self.device)
        # torchaudio.save("/home/wangguisen/projects/tts/test_audio/output/tttt_scoket.wav", torch.from_numpy(warm_audio_chunk).unsqueeze(0), warm_final_sample_rate)

        # print("[DEBUG] Warm-up audio: {}, sr: {}, ref_text: {}".format(audio.shape, warm_final_sample_rate, ref_text))
        # print(f"[DEBUG] Warm-up Min-Max ref_audio value: {torch.min(torch.mean(audio, axis=0)), torch.max(torch.mean(audio, axis=0))}")
        # print(f"[DEBUG] Warm-up Min-Max audio value: {np.min(warm_audio_chunk), np.max(warm_audio_chunk)}")

        print("Warm-up completed.")

    def generate_stream(self, text, play_steps_in_s=0.5):
        """Generate audio in chunks and yield them in real-time.
        接收一个文本输入，并使用 infer_batch_process() 方法生成音频。音频生成后，分成小块进行流式传输。每个音频块的大小由 play_steps_in_s 控制
        """

        # Preprocess the reference audio and text
        ref_audio, ref_text = preprocess_ref_audio_text(self.ref_audio, self.ref_text)

        # Load reference audio
        audio, sr = torchaudio.load(ref_audio)

        # Run inference for the input text
        audio_chunk, final_sample_rate, _ = infer_batch_process(
            (audio, sr),
            ref_text,
            [text],
            self.model,
            self.vocoder,
            device=self.device,  # Pass vocoder here
            nfe_step=32,   # TODO:
            speed=1,
        )

        # print("???? ", type(audio_chunk), audio_chunk.shape, final_sample_rate)
        # print("[DEBUG] audio: {}, sr: {}, ref_text: {}".format(audio.shape, final_sample_rate, ref_text))
        # print(f"[DEBUG] Min-Max ref_audio value: {torch.min(torch.mean(audio, axis=0)), torch.max(torch.mean(audio, axis=0))}")
        # print(f"[DEBUG] Min-Max audio value: {np.min(audio_chunk), np.max(audio_chunk)}")

        # Break the generated audio into chunks and send them
        chunk_size = int(final_sample_rate * play_steps_in_s)

        if len(audio_chunk) < chunk_size:
            packed_audio = struct.pack(f"{len(audio_chunk)}f", *audio_chunk)
            yield packed_audio
            return

        for i in range(0, len(audio_chunk), chunk_size):
            chunk = audio_chunk[i : i + chunk_size]

            # Check if it's the final chunk
            if i + chunk_size >= len(audio_chunk):
                chunk = audio_chunk[i:]

            # Send the chunk if it is not empty
            if len(chunk) > 0:
                packed_audio = struct.pack(f"{len(chunk)}f", *chunk)
                yield packed_audio
